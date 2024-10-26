#include <linux/bpf.h>
#include <linux/in.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <bpf/bpf_helpers.h>

struct host_info {
    __u32 hid;  // Host ID
    __u32 cpu;  // CPU usage percentage
};

// Mapa fixo (pinned) para armazenar a informação do host
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 1);
    __type(key, int);
    __type(value, struct host_info);
    __uint(pinning, LIBBPF_PIN_BY_NAME);
} map_host_info SEC(".maps");

char LICENSE[] SEC("license") = "GPL";
