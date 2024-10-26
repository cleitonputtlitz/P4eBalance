/* -*- P4_16 -*- */
#include <core.p4>
#include <v1model.p4>

#include "INT_headers.h"
#include "LB_headers.h"

const bit<16> TYPE_IPV4 = 0x800;	//2048
const bit<16> TYPE_LB_PATH = 0x1211;
//const bit<8> TYPE_UDP = 0x11;
//const bit<8> TYPE_TCP = 0x06;

//const bit<16> TYPE_IPV4_2     = 0x1215;
const bit<16> TYPE_INT_HEADER = 0x1212;	//4626
const bit<16> TYPE_INT_TRACE  = 0x1213;	//4627
const bit<16> TYPE_INT_HOST   = 0x1214;
const bit<8>  TYPE_RPC        = 0xFD; //0x1215

#define TYPE_UDP 17
#define TYPE_TCP 6
#define DROP_PORT 511

/*************************************************************************
*********************** H E A D E R S  ***********************************
*************************************************************************/

typedef bit<9>  egressSpec_t;
typedef bit<48> macAddr_t;
typedef bit<32> ip4Addr_t;

header ethernet_t {
    macAddr_t dstAddr;
    macAddr_t srcAddr;
    bit<16>   etherType;
}

header ipv4_t {
    bit<4>    version;
    bit<4>    ihl;
    bit<8>    diffserv;
    bit<16>   totalLen;
    bit<16>   identification;
    bit<3>    flags;
    bit<13>   fragOffset;
    bit<8>    ttl;
    bit<8>    protocol;
    bit<16>   hdrChecksum;
    ip4Addr_t srcAddr;
    ip4Addr_t dstAddr;
}//20

header tcp_t {
    bit<16> srcPort;
    bit<16> dstPort;
    bit<32> seqNo;
    bit<32> ackNo;
    bit<4> dataOffset;
    bit<4> res;
    bit<8> flags;
    bit<16> window;
    bit<16> checksum;
    bit<16> urgentPtr;
}//20

header udp_t {
    bit<16> srcPort;
    bit<16> dstPort;
    bit<16> length_;
    bit<16> checksum;
}



struct metadata {
    bit<32> path_index_id;
    bit<8> total_paths;
    bit<32> total_weights;
    bit<32> path_id;
    bit<1> direction;
    bit<1> sw_direction;
    bit<16> srcPort;
    bit<16> dstPort;
    bit<32> path_weight;
    bit<32> current_path_weight;
    bit<32> max_q_depth;
    ip4Addr_t dstAddr;
    ip4Addr_t srcAddr;
    bit<16> tcp_segment_len;
    bit<1> alt_srcAddr;

    @field_list(1)
    bit<8> sw_id;
    //bit<32> sw_id;
    bit<48> freq_collect_INT;
    bit<32> q_traces;
    bit<1>  lastHop;
    bit<32> packet_size;
    @field_list(1)
    bit<9> ingress_port;
    @field_list(1)
    bit<9>  egress_port;
    @field_list(1)
    bit <48> ingress_timestamp;
    @field_list(1)
    bit<19> deq_qdepth;
    @field_list(1)
    bit<32> enq_timestamp;
    @field_list(1)
    bit<19> enq_qdepth;
    @field_list(1)
    bit<32> deq_timedelta;
    @field_list(1)
    bit<48> last_INT_timestamp;
    @field_list(1)
    bit<1> add_INT;
    @field_list(1)
    bit<48> tot_packets;
    bit<24> qtd_drops;
}

struct headers {
    packet_out_header_t packet_out;
    active_path_t[MAX_PATHS] active_path;
    packet_in_header_t packet_in;
    ethernet_t   ethernet;
    ipv4_t       ipv4;
    LB_path_t    LB_path;
    rpc_t                     rpc;
    int_header_t              int_header;
    int_trace_t[MAX_HOPS]     int_trace;
    int_host_t                int_host;
    udp_t        udp;
    tcp_t        tcp;
}
