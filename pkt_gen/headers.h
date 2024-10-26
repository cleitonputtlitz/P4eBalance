#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <time.h>
#include <sys/time.h>
#include <pthread.h>
#include <errno.h>

#include <bpf/libbpf.h>
#include <bpf/bpf.h>
#include <linux/limits.h>

#define BUFFER_SIZE 1500 // Buffer size for received data
#define SERVER_PORT 1234
#define PROC_STAT_PATH_LEN 64

#define BPF_OBJ_PATH "/sys/fs/bpf/xdp/globals/map_host_info"

// Estrutura para armazenar as informações do host
struct host_info {
    __u32 hid;
    __u32 cpu;
};

struct thread_args {
    int pid;
    int host_id;
};

struct RPC {
    unsigned int id;  //32
    unsigned int seq; //32
    unsigned char direction;  // 8
    unsigned char fin;  //8
    //unsigned int offset;
};

struct ThreadData {
    unsigned int rpc_id;
    size_t packet_size;
    long long send_time;
    long long response_time;
};

// Estrutura para o nó da lista encadeada
struct ThreadNode {
    pthread_t thread;                   // Thread criada
    struct ThreadData *data;           // Dados da thread
    struct ThreadNode *next;           // Próximo nó
};

unsigned long long get_time_ns() {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1e9 + ts.tv_nsec;
}

// Function to generate random data for the message
void generate_random_data(unsigned char *data, size_t size) {
    for (size_t i = 0; i < size; ++i) {
        data[i] = rand() % 256;
    }
}

void add_thread_to_end(struct ThreadNode **head, struct ThreadNode **tail, pthread_t thread) {
    struct ThreadNode *new_node = (struct ThreadNode *)malloc(sizeof(struct ThreadNode));
    if (new_node == NULL) {
        perror("Failed to allocate memory for new thread node");
        exit(EXIT_FAILURE);
    }
    new_node->thread = thread;
    new_node->data = NULL; //data
    new_node->next = NULL;

    // Se a lista estiver vazia, o novo nó é tanto a cabeça quanto a cauda
    if (*head == NULL) {
        *head = new_node;
        *tail = new_node;
    } else {
        (*tail)->next = new_node;  // Adiciona o novo nó ao final da lista
        *tail = new_node;          // Atualiza a cauda
    }
}

// Função para remover o primeiro nó da lista encadeada
struct ThreadNode* remove_first_thread(struct ThreadNode **head) {
    if (*head == NULL) {
        return NULL;  // Lista vazia
    }

    struct ThreadNode *removed_node = *head;
    *head = (*head)->next;  // Move a cabeça para o próximo nó
    return removed_node;  // Retorna o nó removido (para processamento ou finalização)
}

void get_process_cpu_time(pid_t pid, unsigned long long *utime, unsigned long long *stime) {
    char proc_stat_path[PROC_STAT_PATH_LEN];
    FILE *fp;
    char buffer[1024];

    snprintf(proc_stat_path, PROC_STAT_PATH_LEN, "/proc/%d/stat", pid);

    fp = fopen(proc_stat_path, "r");
    if (fp == NULL) {
        perror("Erro ao abrir o arquivo stat");
        exit(EXIT_FAILURE);
    }

    if (fgets(buffer, sizeof(buffer), fp) == NULL) {
        perror("Erro ao ler o arquivo stat");
        fclose(fp);
        exit(EXIT_FAILURE);
    }

    fclose(fp);

    char *token;
    int i = 0;
    // Posição 14 e 15 em /proc/<pid>/stat correspondem a utime e stime
    for (token = strtok(buffer, " "); token != NULL; token = strtok(NULL, " ")) {
        if (i == 13) {
            *utime = strtoull(token, NULL, 10); // utime está na posição 14 (index 13)
        } else if (i == 14) {
            *stime = strtoull(token, NULL, 10); // stime está na posição 15 (index 14)
            break;
        }
        i++;
    }
}
