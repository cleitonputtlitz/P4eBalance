
#include "headers.h"

#define SERVER_PORT 1234    // Server port number
#define BUFFER_SIZE 1500     // Buffer size for receiving data
#define REPLY_MESSAGE "Acknowledged"  // Reply message to send back to the client
#define RECV_BUFFER_SIZE 16777216 //16 MB

int tot_connections = 0;
int tot_connections_time = 0;
int finalizar = 0;
int server_socket;

struct ClientData {
    struct sockaddr_in client_addr;
    char buffer[BUFFER_SIZE];
    ssize_t received_size;
};

void* handle_request(void* arg) {
    struct ClientData* client_data = (struct ClientData*) arg;

    // Obter o endereço IP e a porta do cliente
    char client_ip[INET_ADDRSTRLEN];
    inet_ntop(AF_INET, &client_data->client_addr.sin_addr, client_ip, sizeof(client_ip));
    int client_port = ntohs(client_data->client_addr.sin_port);

    // Imprimir a mensagem recebida e o endereço do cliente
    //printf("Received message from (%s, %d) size: %ld bytes)\n", client_ip, client_port, client_data->received_size);


    //int load_factor = 1000000;  // tava antes
    int load_factor = 100000;  // Ajuste para controlar a intensidade da carga
    volatile unsigned long dummy = 0;

    for (int i = 0; i < load_factor; i++) {
        dummy += i * i;  // Operação inútil apenas para consumir CPU
    }

    usleep(1000000/500);

    // Enviar a resposta de volta para o cliente (echo do que foi recebido)
    ssize_t sent_size = sendto(server_socket, client_data->buffer, client_data->received_size, 0,
                               (struct sockaddr *)&client_data->client_addr, sizeof(client_data->client_addr));
    if (sent_size < 0) {
        perror("Sendto failed");
    }

    // Liberar a memória alocada para os dados do cliente
    free(client_data);
    pthread_exit(NULL);  // Termina a thread
}

void* host_monitor(void* arg) {
    //pid_t pid = (pid_t)(intptr_t)arg;
    struct thread_args* args = (struct thread_args*) arg;
    pid_t pid = args->pid;
    int host_id = args->host_id;
    int bpf_map_fd;
    unsigned long long prev_utime = 0, prev_stime = 0;
    unsigned long long curr_utime, curr_stime;
    unsigned long long total_time_prev, total_time_curr;
    int cpu_usage;
    long ticks_per_sec = sysconf(_SC_CLK_TCK);

    get_process_cpu_time(pid, &prev_utime, &prev_stime);
    total_time_prev = prev_utime + prev_stime;

    // Abrir o mapa eBPF fixo (pinned map)
    bpf_map_fd = bpf_obj_get(BPF_OBJ_PATH);
    if (bpf_map_fd < 0) {
        perror("Failed to open pinned BPF map");
        return NULL;
    }

    char filename[50];
    sprintf(filename, "history_host_id%d.log", host_id);

    while (1) {
        sleep(1);

        // Obtenha os tempos de CPU atuais
        get_process_cpu_time(pid, &curr_utime, &curr_stime);
        total_time_curr = curr_utime + curr_stime;

        // Calcule a utilização de CPU como a diferença dos tempos, dividida pelo tempo transcorrido
        //cpu_usage = (int)(total_time_curr - total_time_prev) / ticks_per_sec * 100.0;
        cpu_usage = (int)(((total_time_curr - total_time_prev) * 100.0) / ticks_per_sec);

        //cpu_usage = (int)cpu_usage / 8;

        if(cpu_usage > 100){
          cpu_usage = 100;
        }

        // Atualize os tempos anteriores
        total_time_prev = total_time_curr;

        // Imprima a utilização de CPU
        printf("Pid: %d Connections: %d CPU: %d\n", pid, tot_connections_time, cpu_usage);

        struct host_info info;
        info.hid = htonl(host_id);
        info.cpu = htonl(cpu_usage);

        // Atualizar o mapa eBPF
        int key = 0;
        if (bpf_map_update_elem(bpf_map_fd, &key, &info, BPF_ANY) != 0) {
            perror("Failed to update BPF map");
            break;
        }

        FILE *file = fopen(filename, "a");
        if (file == NULL) {
            perror("Failed to open file");
        }
        fprintf(file, "%d; %d; \n", tot_connections_time, cpu_usage);
        fclose(file);

        tot_connections_time = 0;

        if(finalizar == 1){
          break;
        }
    }

    printf("Finalizando host_monitor\n");

    pthread_exit(NULL);
}


int main(int argc, char *argv[]) {

    if(argc < 2){
      printf("O id do host precisa ser fornecido\n");
      return 1;
    }

    int host_id = atoi(argv[1]);
    printf("host_id...%d\n",host_id);

    pid_t pid = getpid();
    pthread_t thread_monitor;

    struct thread_args args;
    args.pid = pid;
    args.host_id = host_id;
    if (pthread_create(&thread_monitor, NULL, host_monitor, (void*)&args) != 0) {
        perror("Failed to create thread host_monitor");
        exit(EXIT_FAILURE);
    }

    struct sockaddr_in server_addr, client_addr;
    unsigned char buffer[BUFFER_SIZE];
    socklen_t client_addr_len;
    ssize_t received_size;

    // Create a UDP socket
    server_socket = socket(AF_INET, SOCK_DGRAM, 0);
    if (server_socket < 0) {
        perror("Socket creation failed");
        exit(EXIT_FAILURE);
    }

    // Aumente o tamanho do buffer de recepção do socket
    int recv_buf_size = RECV_BUFFER_SIZE;
    if (setsockopt(server_socket, SOL_SOCKET, SO_RCVBUF, &recv_buf_size, sizeof(recv_buf_size)) < 0) {
        perror("Set socket receive buffer size failed");
        close(server_socket);
        exit(EXIT_FAILURE);
    }

    // Set up the server address
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(SERVER_PORT);
    server_addr.sin_addr.s_addr = INADDR_ANY;

    // Bind the socket to the server address and port
    if (bind(server_socket, (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
        perror("Bind failed");
        close(server_socket);
        exit(EXIT_FAILURE);
    }

    struct timeval timeout;
    timeout.tv_sec = 90;   // 10 seconds
    timeout.tv_usec = 0;   // 0 microseconds
    if (setsockopt(server_socket, SOL_SOCKET, SO_RCVTIMEO, (const char*)&timeout, sizeof(timeout)) < 0) {
        perror("Set socket timeout failed");
        close(server_socket);
        exit(EXIT_FAILURE);
    }

    printf("Server is listening on port %d...\n", SERVER_PORT);

    while (1) {
        // Receive data from the client
        client_addr_len = sizeof(client_addr);
        received_size = recvfrom(server_socket, buffer, BUFFER_SIZE, 0,
                                 (struct sockaddr *)&client_addr, &client_addr_len);

        if (received_size < 0) {
            if (errno == EAGAIN || errno == EWOULDBLOCK) {
                // Timeout occurred
                printf("Timeout occurred: no data received for 10 seconds.\n");
                break; // Exit the loop if timeout
            } else {
              perror("Recvfrom failed");
              continue;
            }
        }

        /*
        //printf("Received message from client (size: %ld bytes)\n", received_size);
        // Obter o endereço IP e a porta do cliente
        char client_ip[INET_ADDRSTRLEN];
        inet_ntop(AF_INET, &client_addr.sin_addr, client_ip, sizeof(client_ip));
        int client_port = ntohs(client_addr.sin_port);

        // Imprimir a mensagem recebida e o endereço do cliente
        printf("Received message from (%s, %d) size: %ld bytes)\n", client_ip, client_port, received_size);
        */

        tot_connections += 1;
        tot_connections_time += 1;

        struct ClientData* client_data = malloc(sizeof(struct ClientData));
        if (client_data == NULL) {
            perror("Failed to allocate memory");
            continue;
        }

        client_data->client_addr = client_addr;
        memcpy(client_data->buffer, buffer, received_size);
        client_data->received_size = received_size;

        // Criar uma nova thread para processar a requisição
        pthread_t thread;
        if (pthread_create(&thread, NULL, handle_request, client_data) != 0) {
            perror("Failed to create thread");
            free(client_data);  // Liberar a memória se falhar ao criar a thread
            continue;
        }

        pthread_detach(thread); //Desvincula a thread principal da thread criada

        /*
        // Extract the RPC structure from the received message
        if (received_size >= sizeof(struct RPC)) {
            struct RPC *rpc = (struct RPC *)buffer;
            printf("RPC ID: %u\n", rpc->id);
            printf("RPC Sequence: %hu\n", rpc->seq);
            printf("RPC Direction: %hhu\n", rpc->direction);
            printf("RPC FIN: %hhu\n", rpc->fin);
            printf("RPC Offset: %u\n", rpc->offset);
        } else {
            printf("Received packet is too small to contain an RPC structure.\n");
        }
        */

        // Send reply message to the client
        //ssize_t sent_size = sendto(server_socket, buffer, strlen(buffer), 0,
        //                         (struct sockaddr *)&client_addr, client_addr_len);



        /*
        if (sent_size < 0) {
            perror("Sendto failed");
        } else {
            printf("Sent reply to client: \n");
        }
        */
    }

    printf("tot_connections %d\n", tot_connections);

    char filename[50];
    sprintf(filename, "host_id%d.log", host_id);

    FILE *file = fopen(filename, "a");
    if (file != NULL) {
      fprintf(file, "tot_connections %d\n", tot_connections);

      fclose(file);
    }

    finalizar = 1;
    pthread_join(thread_monitor, NULL);

    close(server_socket);
    return 0;
}
