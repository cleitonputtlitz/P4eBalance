/* -*- P4_16 -*- */
#include <core.p4>
#include <v1model.p4>


#define CPU_PORT 255  //p4runtime_switch.py, commands.txt
#define NUM_PATHS 1024
#define MAX_PATHS 10
#define MAX_WCMP_LENGHT 50  //10 caminhos com peso máximo de 5 para cada caminho
#define NUM_DSTS 1

#define BLOOM_FILTER_ENTRIES 65536	//aumentar esse tamanho TODO

#define CONNTABLE_SIZE 65536

#define SIZE_LB_PATH 7
#define SIZE_PKT_IN 4



/*************************************************************************
*********************** H E A D E R S  ***********************************
*************************************************************************/

header LB_path_t {
    bit<32> path_id;
    bit<1>  direction;
    bit<16> proto_id;
    bit<7>  offset;
}

header active_path_t {
    bit<32> path_id;
    bit<32> path_weight;
}

@controller_header("packet_in")	//telemetry metrics
header packet_in_header_t {
    bit<32>  sw_id;
//source: https://github.com/opennetworkinglab/ngsdn-tutorial/blob/advanced/solution/p4src/main.p4
}

@controller_header("packet_out")
header packet_out_header_t {
    bit<8> total_paths;
}


//A P4 register is liked an “array”. It is an array of values, all with the same type.
//Read an write retrieves/modifies the value stored in the array at one index

//Stored state for each path_id
register<bit<32>>(NUM_PATHS) stored_state1; //q_depth
register<bit<32>>(NUM_PATHS) stored_state2; //cpu


register<bit<48>>(NUM_PATHS) last_path_weight_atz;


//WCMPTable
register<bit<32>>(NUM_DSTS) weight0;        // mapping from pathId to weight
register<bit<32>>(NUM_DSTS) weight1;        // mapping from pathId to weight
register<bit<32>>(NUM_DSTS) weight2;        // mapping from pathId to weight
register<bit<32>>(NUM_DSTS) weight3;        // mapping from pathId to weight
register<bit<32>>(NUM_DSTS) weight4;        // mapping from pathId to weight
register<bit<32>>(NUM_DSTS) weight5;        // mapping from pathId to weight
//    register<bit<32>>(NUM_DSTS) weight6;        // mapping from pathId to weight
//    register<bit<32>>(NUM_DSTS) weight7;        // mapping from pathId to weight
register<bit<32>>(NUM_DSTS) range0;         // HashBucket range
register<bit<32>>(NUM_DSTS) range1;         // HashBucket range
register<bit<32>>(NUM_DSTS) range2;         // HashBucket range
register<bit<32>>(NUM_DSTS) range3;         // HashBucket range
register<bit<32>>(NUM_DSTS) range4;         // HashBucket range
register<bit<32>>(NUM_DSTS) range5;         // HashBucket range
//    register<bit<16>>(NUM_DSTS) range6;         // HashBucket range
//    register<bit<16>>(NUM_DSTS) range7;         // HashBucket range
register<bit<32>>(NUM_DSTS) sumWeight;


register<bit<1>>(BLOOM_FILTER_ENTRIES) bloom_filter_1;
register<bit<1>>(BLOOM_FILTER_ENTRIES) bloom_filter_2;

/*
A bloom filter with two hash functions is used to check if a packet is a part of an existing flow.
An action (called compute_hashes) to compute the bloom filter's two hashes using hash algorithms crc16 and crc32.
The hashes will be computed on the packet 5-tuple consisting of IPv4 source and destination addresses, source and destination port numbers and the IPv4 protocol type.

The optimal number of hash functions is usually calculated based on the size of the bit array and the expected number of elements.

Two different register arrays is used for the bloom filter, each to be updated by a different hash function.
Using different register arrays makes our design amenable to high-speed P4 targets that typically allow only one access to a register array per packet.

*/


//ConnTable
//index -> path_id
register<bit<32>>(CONNTABLE_SIZE) ConnTable;
