/* -*- P4_16 -*- */
#include <core.p4>
#include <v1model.p4>


#define PKT_INSTANCE_TYPE_NORMAL 0
#define PKT_INSTANCE_TYPE_INGRESS_CLONE 1
#define PKT_INSTANCE_TYPE_EGRESS_CLONE 2
#define PKT_INSTANCE_TYPE_RECIRC 4
#define PKT_INSTANCE_TYPE_RESUBMIT 6

#ifndef COLLECT_SIZE
#define COLLECT_SIZE 0
#endif

#define SIZE_INT_HEADER 4
#define SIZE_INT_HOST 14 //18
#define SIZE_ETHERNET 14
#define SIZE_IPv4 20
#define SIZE_RPC 8  //4
#define SIZE_UDP 8
#define SIZE_NORMAL_PKT SIZE_ETHERNET + SIZE_IPv4 + SIZE_UDP

#define MAX_HOPS 20


/*************************************************************************
*********************** H E A D E R S  ***********************************
*************************************************************************/


header rpc_t {
    bit<32> id;
    bit<32> seq;
} //6 Bytes

header int_header_t {
    bit<32> q_traces;
}

#if COLLECT_SIZE == 0
  #define SIZE_INT_TRACE 15
#else
#if COLLECT_SIZE == 1
  #define SIZE_INT_TRACE 9
#else
  #if COLLECT_SIZE == 2
    #define SIZE_INT_TRACE 36
  #else
    #if COLLECT_SIZE == 3
      #define SIZE_INT_TRACE 72
    #else //alto discretizado
      #define SIZE_INT_TRACE 43
    #endif
  #endif
#endif
#endif

#if COLLECT_SIZE == 0
  header int_trace_t {
      bit<8>   swid;
      bit<48>  q_delay; //Stores deq_timestamp - enq_timestamp
      bit<24>  q_depth; //Stores the current number of packets in the queue
      bit<24>  q_drops; //Stores the number of packet drops
      bit<16>  next_proto;
      //120 bits (15 Bytes)
  }
#else
#if COLLECT_SIZE == 1
  header int_trace_t {
      bit<32>  swid;
      bit<19>  enq_qdepth;
      bit<5>   padding;
      bit<16>  next_proto;
      //72 bits (9 Bytes)
  }
#else
  #if COLLECT_SIZE == 2
    header int_trace_t {
      bit<32> swid;
      bit<9>  ingress_port;
      bit<9>  egress_port;
      bit<32> enq_timestamp;
      bit<19> enq_qdepth;
      bit<32> deq_timedelta;//the time, in microseconds, that the packet spent in the queue.
      bit<19> deq_qdepth; //the depth of queue when the packet was dequeued, in units of number of packets
      bit<48> ingress_timestamp;
      bit<48> egress_timestamp;
      bit<24> qtd_drops;
      bit<16>  next_proto;
      //288 bits (36 Bytes)
    }
  #else
    #if COLLECT_SIZE == 3
      header int_trace_t {
        bit<32> swid;
        bit<9>  ingress_port;
        bit<9>  egress_port;
        bit<32> enq_timestamp;
        bit<19> enq_qdepth;
        bit<32> deq_timedelta;
        bit<19> deq_qdepth;
        bit<48> ingress_timestamp;
        bit<48> egress_timestamp;
        bit<64> int_field_1;
        bit<64> int_field_2;
        bit<64> int_field_3;
        bit<64> int_field_4;
        bit<48> int_field_5;
        bit<8>  int_field_6;
        bit<16>  next_proto;
        //576 bits (72 Bytes)
      }
    #else
      //#if COLLECT_SIZE == 4 //Otimizado discretizado
        header int_trace_t {
          bit<8>  swid; //bit<32>  swid;
          bit<9>  ingress_port;
          bit<9>  egress_port;
          bit<32> enq_timestamp;
          bit<2>  enq_qdepth; //bit<19> enq_qdepth;
          bit<32> deq_timedelta;
          bit<2>  deq_qdepth; //bit<19> deq_qdepth;
          //bit<48> ingress_timestamp;
          //bit<48> egress_timestamp;
          bit<2> int_field_1;  //packet_length
          bit<48> int_field_2;  //egress_timestamp-ingress_timestamp
          bit<64> int_field_3;
          bit<64> int_field_4;
          bit<48> int_field_5;  //last_INT_timestamp;
          bit<8>  int_field_6;
          bit<16>  next_proto;
          //344 bits (43 Bytes) economia de 29 bytes
        }
      //#endif
    #endif
  #endif
#endif
#endif


header int_host_t {
    bit<32> hid;
    bit<32> cpu;
    //bit<64> tx_reqs;
    //bit<64> time_reqs;
    bit<16>  next_proto;
} //80 bits (10 Bytes)


register<bit<48>>(960) last_INT_timestamp;
register<bit<48>>(960) tot_packets;
register<bit<24>>(1) qtd_drops;
