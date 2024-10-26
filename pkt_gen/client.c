
#include "headers.h"

  //gcc -o udp_client client.c -lpthread

#define PACKET_SIZE (10 * 1024 / 8) // Size of data
#define TIMEOUT 20 // Timeout in seconds
#define NUM_THREADS 10


int total_threads = 0;
int count = 0;
int finalizar = 0;

struct ThreadNode *head = NULL;
struct ThreadNode *tail = NULL;

void* udp_request(void* arg) {
    int client_socket;
    struct sockaddr_in server_addr;
    unsigned char buffer[BUFFER_SIZE];
    unsigned long long send_time, response_time;
    double duration = 0;
    ssize_t received_size;

    // Create a UDP socket
    client_socket = socket(AF_INET, SOCK_DGRAM, 0);
    if (client_socket < 0) {
        perror("Socket creation failed");
        exit(EXIT_FAILURE);
    }

    // Set up the server address structure
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(SERVER_PORT);
    inet_pton(AF_INET, "10.0.10.10", &server_addr.sin_addr);

    // Prepare the RPC message
    struct RPC rpc;
    rpc.id = htonl(rand() & 0x7FFFFFFF); // Random 31-bit value
    rpc.seq = htonl(1);
    rpc.direction = htonl(0);
    rpc.fin = htonl(1);
    //rpc.offset = 0;

    // Generate random data
    unsigned char payload[PACKET_SIZE];
    generate_random_data(payload, PACKET_SIZE);

    // Build the message (RPC header + random data)
    memcpy(buffer, &rpc, sizeof(rpc));
    memcpy(buffer + sizeof(rpc), payload, PACKET_SIZE);

    // Record send time
    send_time = get_time_ns();

    // Send the message to the server
    ssize_t sent_size = sendto(client_socket, buffer, sizeof(rpc) + PACKET_SIZE, 0,
                               (struct sockaddr *)&server_addr, sizeof(server_addr));

    //printf("Enviando RPC id %d\n", ntohl(rpc.id));

    if (sent_size < 0) {
        perror("Sendto failed");
        close(client_socket);
        exit(EXIT_FAILURE);
    }

    // Set socket timeout option
    struct timeval timeout;
    timeout.tv_sec = TIMEOUT;
    timeout.tv_usec = 0;
    if (setsockopt(client_socket, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) < 0) {
        perror("Setsockopt failed");
        close(client_socket);
        exit(EXIT_FAILURE);
    }

    // Try to receive the response from the server
    socklen_t addr_len = sizeof(server_addr);
    received_size = recvfrom(client_socket, buffer, BUFFER_SIZE, 0,
                             (struct sockaddr *)&server_addr, &addr_len);

    if (received_size < 0) {
        //perror("Recvfrom timed out or failed");
        response_time = 0;
        duration = 0;
    } else {
        // Record end time and calculate duration
        response_time = get_time_ns();
        duration = (send_time - response_time) / 1e9;
        //printf("Received response, total duration: %.9f seconds\n", duration);
    }

    //printf("Finish after %.9f seconds\n", duration);

    struct ThreadData* data = malloc(sizeof(struct ThreadData));
    if (data != NULL) {
        data->rpc_id = ntohl(rpc.id);
        data->packet_size = PACKET_SIZE;  //TODO
        data->send_time = send_time;
        data->response_time = response_time;
    } else {
      perror("Erro ao finalizar thread");
    }
    /*
    printf("%u,%zu,%lld,%lld\n",
            data->rpc_id,
            data->packet_size,
            data->send_time,
            data->response_time);
            */
    // Close the socket
    close(client_socket);
    pthread_exit(data);  // Retorna os dados da execucao
}

void* create_threads(void* arg) {
    srand(time(NULL));
    time_t inicio, now;
    double tempo_decorrido;
    time(&inicio);
    int count = 0;

    while (1) {
        time(&now);
        tempo_decorrido = difftime(now, inicio);

        if (tempo_decorrido >= 10*60) { //900=15minutos
            break;
        }

        struct timespec start_time, end_time;
        clock_gettime(CLOCK_MONOTONIC, &start_time); // Início da contagem de tempo

        count += 1;

        //printf("Threads criadas %d\n",count);

        /*
        // Realiza realloc para aumentar o tamanho dos arrays de threads e resultados
        threads = realloc(threads, count * sizeof(pthread_t));
        results = realloc(results, count * sizeof(struct ThreadData*));
        if (threads == NULL || results == NULL) {
            perror("Memory allocation failed");
            exit(EXIT_FAILURE);
        }
        */

        // Criar múltiplas threads para enviar requisições simultâneas
        //for (int i = 0; i < NUM_THREADS; i++) {
          /*
            struct ThreadData *data = (struct ThreadData *)malloc(sizeof(struct ThreadData));
            if (data == NULL) {
                perror("Failed to allocate memory for ThreadData");
                exit(EXIT_FAILURE);
            }
            */
            pthread_t thread;
            if (pthread_create(&thread, NULL, udp_request, NULL) != 0) {
                perror("Failed to create thread");
                //free(data); // Libera a memória alocada para os dados
                exit(EXIT_FAILURE);
            }
            /*
            if (pthread_create(&threads[total_threads + i], NULL, udp_request, NULL) != 0) {
                perror("Failed to create thread");
                exit(EXIT_FAILURE);
            }
            */

            //add_thread_to_end(&head, &tail, thread, data);
            add_thread_to_end(&head, &tail, thread);
            total_threads++;

            //pthread_detach(thread);

            //usleep(1000000/185); //Pausa de 1s / numero threads ESSE E O QUE TAVA ATE AGORA

            usleep(1000000/480); //Pausa de 1s / numero threads

          //  usleep(1000000);  //pausa de 1 segundo
      //  }

        total_threads += NUM_THREADS;

    }

    printf("create_threads finished. Enviados %d\n", count);
    finalizar = 1;
    pthread_exit(NULL);  // Finaliza a thread de criação
}

void* process_results(void* arg) {
    // Gravar os resultados no arquivo CSV
    char *filename = (char *)arg;
    FILE *file = fopen(filename, "a");
    if (file == NULL) {
        perror("Failed to open file");
        return NULL;
    }

    // Se o arquivo é novo, escrever o cabeçalho
    fseek(file, 0, SEEK_END);
    if (ftell(file) == 0) {
        fprintf(file, "rpc_id,packet_size,send_time_ns,response_time_ns\n");
    }

    usleep(100000);

    int count = 0;

   printf("Process_results...\n");

   struct ThreadNode *current;
   void *ret_val;
   int res = 0;

    while(1) {

      // Esperar todas as threads terminarem e coletar resultados
      //for (int i = 0; i < total_threads; i++) {

         //printf("Process_results. Count %d\n",count);

          current = remove_first_thread(&head);

          if(current != NULL) {

              res = pthread_join(current->thread, &ret_val); // Espera a thread terminar

              if (res != 0) {
                  printf("pthread_join failed with error code: %d\n", res);
              } else {

                current->data = (struct ThreadData*)ret_val;

                if (current->data != NULL) {
                  /*
                  printf("%u,%zu,%lld,%lld\n",
                            current->data->rpc_id,
                            current->data->packet_size,
                            current->data->send_time,
                            current->data->response_time);
                    */
                    fprintf(file, "%u,%zu,%lld,%lld\n",
                            current->data->rpc_id,
                            current->data->packet_size,
                            current->data->send_time,
                            current->data->response_time);
                }
                else {
                  printf("Thread nao retornou dados\n");
                }
                //free(head); // Libera os dados da thread
                free(current->data); // Libera os dados da thread

              }
              free(current);       // Libera o nó da lista
              count += 1;
          }
            else {
              if(finalizar == 1) {
                break;
              }
            usleep(100000);
          }
      //}

    }
    printf("process thread finalizado. Processados %d\n", count);
    fclose(file);
    pthread_exit(NULL);  // Finaliza a thread de processamento
}

int main(int argc, char *argv[]) {

    if(argc < 2){
      printf("O nome do arquivo precisa ser fornecido\n");
      return 1;
    }

    printf("Enviando dados...\n");
    char *filename = argv[1];

    pthread_t thread_creator, thread_processor;
    unsigned long long init_time, end_time;
    double duration = 0;

    init_time = get_time_ns();

    // Criar a thread responsável por gerar novas threads
    if (pthread_create(&thread_creator, NULL, create_threads, NULL) != 0) {
        perror("Failed to create thread for creating threads");
        exit(EXIT_FAILURE);
    }

    // Criar a thread responsável por processar os resultados
    if (pthread_create(&thread_processor, NULL, process_results, (void *)filename) != 0) {
        perror("Failed to create thread for processing results");
        exit(EXIT_FAILURE);
    }

    // Aguardar ambas as threads finalizarem
    pthread_join(thread_creator, NULL);
    pthread_join(thread_processor, NULL);

    // Liberar memória alocada para threads e resultados
    //free(threads);
    //free(results);

    end_time = get_time_ns();
    duration = (end_time - init_time) / 1e9;
    printf("Finish after %.9f seconds\n", duration);

    return 0;
}
