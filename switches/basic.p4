/* -*- P4_16 -*- */
#include <core.p4>
#include <v1model.p4>
#include "p4headers.h"


/*************************************************************************
*********************** P A R S E R  ***********************************
*************************************************************************/

parser MyParser(packet_in packet,
                out headers hdr,
                inout metadata meta,
                inout standard_metadata_t standard_metadata) {

    state start {
        transition select(standard_metadata.ingress_port){
            CPU_PORT: parse_packet_out;
            default: parse_ethernet;
        }
    }

    //packet_out is a packet sent out of the controller to the switch,
    // which becomes a packet received by the switch on port CPU_PORT.

    // A packet sent by the switch to port CPU_PORT becomes a PacketIn
    // message to the controller.

    state parse_packet_out {
        packet.extract(hdr.packet_out);
        meta.total_paths = hdr.packet_out.total_paths;
        transition select(hdr.packet_out.total_paths){
            0: accept;
            default: parse_active_path;
        }
        //https://github.com/jafingerhut/p4-guide/blob/master/ptf-tests/packetinout/packetinout.p4
    }

    state parse_active_path {
        packet.extract(hdr.active_path.next);
        meta.total_paths = meta.total_paths - 1;
        transition select(meta.total_paths){
            0: accept;
            default: parse_active_path;
        }
    }

    state parse_ethernet {
        packet.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            TYPE_IPV4: parse_ipv4;
            TYPE_LB_PATH: parse_lb_path;
            TYPE_INT_HEADER: parse_int_header;
            default: accept;
        }
    }

    state parse_lb_path {
        packet.extract(hdr.LB_path);
        transition select(hdr.LB_path.proto_id) {
            TYPE_IPV4: parse_ipv4;
            TYPE_INT_HEADER: parse_int_header;
            default: accept;
        }
    }

    state parse_int_header {
        packet.extract(hdr.int_header);
        meta.q_traces = hdr.int_header.q_traces;
        transition select(hdr.int_header.q_traces) {
            0: parse_ipv4;
            default: parse_int_trace;
        }
    }

    state parse_int_trace {
        packet.extract(hdr.int_trace.next);


        if((bit<32>) hdr.int_trace[0].q_depth > meta.max_q_depth){
            meta.max_q_depth = (bit<32>) hdr.int_trace[0].q_depth;
        }

        transition select(hdr.int_trace.last.next_proto) {
            TYPE_INT_TRACE: parse_int_trace;
            TYPE_INT_HOST: parse_int_host;
            TYPE_IPV4: parse_ipv4;
        }
    }

    state parse_int_host {
        packet.extract(hdr.int_host);
        meta.q_traces = meta.q_traces + 1;
        transition select(hdr.int_host.next_proto) {
            TYPE_INT_TRACE: parse_int_trace;
            TYPE_IPV4: parse_ipv4;
        }
    }

    state parse_ipv4 {
        packet.extract(hdr.ipv4);
        transition select(hdr.ipv4.protocol) {
            TYPE_TCP: parse_tcp;
            TYPE_UDP: parse_udp;
            default: accept;
        }
    }

    state parse_udp {
        packet.extract(hdr.udp);
        meta.srcPort = hdr.udp.srcPort;
        meta.dstPort = hdr.udp.dstPort;
        transition check_parse_rpc_src;
    }

    state check_parse_rpc_src {
        transition select(meta.srcPort){
        	1234: parse_rpc;
        	default: check_parse_rpc_dst;
        }
    }

    state check_parse_rpc_dst {
        transition select(meta.dstPort){
        	1234: parse_rpc;
        	default: accept;
        }
    }

    state parse_tcp {
        packet.extract(hdr.tcp);
        meta.srcPort = hdr.tcp.srcPort;
        meta.dstPort = hdr.tcp.dstPort;
        transition check_parse_rpc_src;
    }

    state parse_rpc {
      packet.extract(hdr.rpc);
      transition accept;
    }

}

/*************************************************************************
************   C H E C K S U M    V E R I F I C A T I O N   *************
*************************************************************************/

control MyVerifyChecksum(inout headers hdr, inout metadata meta) {
    apply {  }
}


/*************************************************************************
**************  I N G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyIngress(inout headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t standard_metadata) {


	bit<32> reg_pos_one = 0;
	bit<32> reg_pos_two = 0;
	bit<32> reg_pos_ConnTable = 0;
	bit<1> reg_val_one = 0;
	bit<1> reg_val_two = 0;

    //NUM_DSTS = numero de destinos possíveis
    //para cada destino, vários caminhos.
    //cada caminho com diferentes pesos.
    //NO NOSSO CASO,NUM_DSTS SERÁ SEMPRE 1.
    //Consideraremos apenas vários caminhos com diferentes pesos.


	action drop() {
        mark_to_drop(standard_metadata);
    }

    action send_to_cpu() {
        standard_metadata.egress_spec = CPU_PORT;
    }

    action set_LB_path_header() {
    	hdr.LB_path.setValid();
  		hdr.LB_path.path_id = 0;
  		hdr.LB_path.direction = meta.sw_direction;
  		hdr.LB_path.proto_id = hdr.ethernet.etherType;
  		hdr.LB_path.offset = 0;
  		hdr.ethernet.etherType = TYPE_LB_PATH;
    }

    action compute_hashes(ip4Addr_t srcAddr, bit<16> srcPort, bit<16> dstPort ) {

    	//log_msg("Value1 = {}, Value2 = {}, Value3 = {}, Value4 = {}", {hdr.ipv4.srcAddr, hdr.ipv4.dstAddr, hdr.tcp.srcPort, hdr.tcp.dstPort});
    	log_msg("hdr.ethernet={}", {hdr.ethernet});
    	log_msg("hdr.ipv4={}", {hdr.ipv4});
    	log_msg("hdr.tcp={}", {hdr.tcp});

    	hash(reg_pos_one,
            HashAlgorithm.crc16,
            (bit<32>)0,	//base
            { srcAddr,  //hdr.ipv4.srcAddr,
              //dstAddr, //hdr.ipv4.dstAddr,
              hdr.ipv4.protocol,
              srcPort, //hdr.tcp.srcPort,
              dstPort }, //hdr.tcp.dstPort
            (bit<32>)BLOOM_FILTER_ENTRIES);  //max

    	hash(reg_pos_two,
            HashAlgorithm.crc32,
            (bit<32>)0,	//base
            { srcAddr,
              //dstAddr,
              hdr.ipv4.protocol,
              srcPort,
              dstPort },
            (bit<32>)BLOOM_FILTER_ENTRIES);  //max
	}

	action get_flow_id(ip4Addr_t srcAddr, bit<16> srcPort, bit<16> dstPort) {

        hash(reg_pos_ConnTable,
            HashAlgorithm.crc32,
            (bit<32>)0,	//base
            { srcAddr,
              //dstAddr,
              hdr.ipv4.protocol,
              srcPort,
              dstPort },
            (bit<32>)CONNTABLE_SIZE);  //max TODO
    }

    action set_LB_path(egressSpec_t port, bit<1> lastHop, bit<1> direction){
      standard_metadata.egress_spec = port;
      //hdr.ethernet.srcAddr = hdr.ethernet.dstAddr;
      //hdr.ethernet.dstAddr = dstAddr;
      //hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
      meta.lastHop = lastHop;
      meta.direction = direction;
    }

    action path_select_tcp(bit<16> ecmp_base, bit<32> ecmp_count) {
            hash(meta.path_index_id,
                HashAlgorithm.crc32,
                ecmp_base,
                { hdr.ipv4.srcAddr,
                  hdr.ipv4.dstAddr,
                  hdr.ipv4.protocol,
                  hdr.tcp.srcPort,
                  hdr.tcp.dstPort },
                ecmp_count);
    }

    action path_select_udp(bit<16> ecmp_base, bit<32> ecmp_count){
            hash(meta.path_index_id,
                HashAlgorithm.crc32,
                ecmp_base,
                { hdr.ipv4.srcAddr,
                  hdr.ipv4.dstAddr,
                  hdr.ipv4.protocol,
                  hdr.udp.srcPort,
                  hdr.udp.dstPort },
                ecmp_count);
    }

    action ipv4_forward(macAddr_t dstAddr, egressSpec_t port) {
        standard_metadata.egress_spec = port;
        hdr.ethernet.srcAddr = hdr.ethernet.dstAddr;
        hdr.ethernet.dstAddr = dstAddr;
        hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
    }

    table ipv4_lpm {
        key = {
            hdr.ipv4.dstAddr: lpm;
        }
        actions = {
            ipv4_forward;
            drop;
            NoAction;
        }
        size = 1024;
        default_action = NoAction();
    }

	action get_switch_config(bit<8> swid, bit<48> freq_collect_INT, bit<1> sw_direction) {
		meta.sw_id = swid;
		meta.freq_collect_INT = freq_collect_INT;
		meta.sw_direction = sw_direction;
	}

    action get_weight_config(bit<32> weight) {
        meta.path_weight = weight;
    }

    table path_table {
      key = {
          hdr.LB_path.path_id: exact;
          hdr.LB_path.direction: exact;
      }
      actions = {
        set_LB_path;
        NoAction;
      }
      size = 2048;
      default_action = NoAction();
    }

    table sw_config {
    	actions = {
    		get_switch_config;
    		NoAction;
		  }
		  default_action = NoAction();
    }

    table weight_table {
      key = {
          meta.current_path_weight: exact;
      }
    	actions = {
    		get_weight_config;
    		NoAction;
		  }
		  default_action = NoAction();
    }

    action change_srcAddr(bit<32> srcAddr) {
        hdr.ipv4.srcAddr = srcAddr;
        meta.alt_srcAddr = 1;
    }

    table snat_table {
        key = {
            hdr.ipv4.srcAddr: lpm;
        }
        actions = {
            change_srcAddr;
            NoAction;
        }
        size = 1024;
        default_action = NoAction;
    }

   action change_dstAddr(bit<32> dstAddr) {
        hdr.ipv4.dstAddr = dstAddr;
        meta.alt_srcAddr = 1;
    }

    table dnat_table {
        key = {
            hdr.ipv4.dstAddr: lpm;
            hdr.LB_path.path_id: exact;
        }
        actions = {
            change_dstAddr;
            NoAction;
        }
        size = 1024;
        default_action = NoAction;
    }

    apply {

        if(!hdr.ipv4.isValid() && !hdr.packet_out.isValid()) {
            exit;
        }

        sw_config.apply();

    	if (hdr.packet_out.isValid()) {
       	    // Process packet from controller
    		bit<32> total_weights = 0;

			if(hdr.active_path[0].isValid()) {
				range0.write(0, hdr.active_path[0].path_weight);
				weight0.write(0, hdr.active_path[0].path_id);
				total_weights = total_weights + (bit<32>)hdr.active_path[0].path_weight;
			} else {
				weight0.write(0, 0);
                range0.write(0, 0);
            }

			if(hdr.active_path[1].isValid()) {
				total_weights = total_weights + (bit<32>)hdr.active_path[1].path_weight;
				range1.write(0, total_weights);
				weight1.write(0, hdr.active_path[1].path_id);
			} else {
				weight1.write(0, 0);
                range1.write(0, 0);
            }

			if(hdr.active_path[2].isValid()) {
				total_weights = total_weights + (bit<32>)hdr.active_path[2].path_weight;
				range2.write(0, total_weights);
				weight2.write(0, hdr.active_path[2].path_id);
			} else {
				weight2.write(0, 0);
                range2.write(0, 0);
            }

			if(hdr.active_path[3].isValid()) {
				total_weights = total_weights + (bit<32>)hdr.active_path[3].path_weight;
				range3.write(0, total_weights);
				weight3.write(0, hdr.active_path[3].path_id);
			} else {
				weight3.write(0, 0);
                range3.write(0, 0);
            }

			if(hdr.active_path[4].isValid()) {
				total_weights = total_weights + (bit<32>)hdr.active_path[4].path_weight;
				range4.write(0, total_weights);
				weight4.write(0, hdr.active_path[4].path_id);
			} else {
				weight4.write(0, 0);
                range4.write(0, 0);
            }

			if(hdr.active_path[5].isValid()) {
				total_weights = total_weights + (bit<32>)hdr.active_path[5].path_weight;
				range5.write(0, total_weights);
				weight5.write(0, hdr.active_path[5].path_id);
			} else {
				weight5.write(0, 0);
                range5.write(0, 0);
            }

			sumWeight.write(0, total_weights);

            //meta.last_path_weight_atz = standard_metadata.ingress_global_timestamp;
            //last_path_weight_atz.write(0, meta.last_path_weight_atz);

            drop();
            exit; //exit the pipeline
        }

        meta.alt_srcAddr = 0;

        //na volta troca o srcAdr
        //meta.srcAddr = hdr.ipv4.srcAddr;
        snat_table.apply();

        if(hdr.tcp.isValid()){
            meta.tcp_segment_len = (bit<16>)(hdr.ipv4.totalLen - 16w20);
        } else {
            meta.tcp_segment_len = (bit<16>)(hdr.ipv4.totalLen - 16w20); //(bit<16>)(hdr.ipv4.totalLen - (hdr.ipv4.ihl * 4));
        }


        //****************************** UPDATE PATH STATE **********************************************
        if(hdr.LB_path.isValid() && meta.sw_direction == 0 && hdr.int_host.isValid() && hdr.int_trace[0].isValid()) { //TODO
            bit<48> last_time;
            meta.path_id = hdr.LB_path.path_id;
            //last_path_weight_atz.read(last_time, meta.path_id); //tempo da ultima atualizaçao de peso do caminho
            last_path_weight_atz.read(last_time, 0);

            //update weights after 100us  TODO
            if(standard_metadata.ingress_global_timestamp - last_time >= 100000) {  //100 ms (100000 nanosegundos)

                log_msg("ATUALIZANDO STATUS DO CAMINHO={}", {meta.path_id});

                //1. Get the stored metrics for the path (previous_value)
                bit<32> stored_q_depth;
                bit<32> stored_cpu;
                stored_state1.read(stored_q_depth, meta.path_id) ; //q_depth
                stored_state2.read(stored_cpu, meta.path_id); //cpu

                //2. The current value is inside the INT headers
                //meta.max_q_depth (parser)
                //hdr.int_host.cpu
                meta.max_q_depth = (meta.max_q_depth * 102) >> 10;

                //3. Calculate the EWMA of q_depth and cpu
                //avg_next = ((1-lambda) * avg_previous) + (alpha * q_depth)

                //0.75 * current_value + 0.25 * avg_previous

                stored_q_depth=((meta.max_q_depth >> 1)+(meta.max_q_depth >> 2))+(stored_q_depth>>2);

                stored_cpu = ((hdr.int_host.cpu>>1)+(hdr.int_host.cpu>>2))+(stored_cpu);

                //https://github.com/jafingerhut/p4-guide/blob/master/docs/floating-point-operations.md

                //4. Write values back to registers
                stored_state1.write(meta.path_id, stored_q_depth);
                stored_state2.write(meta.path_id, stored_cpu);

                //5. Calculate the current state ****************
                //bit<32> alpha = 60;
                //bit<32> betha = 40;
                bit<32> new_state = 0;

                //stored_q_depth = (stored_q_depth << 6); // Multiply by 64 (approx 64%)
                //stored_cpu = (stored_cpu << 5);         // Multiply by 32 (approx 32%)

                //new_state = (stored_q_depth + stored_cpu) >> 7; // Normalize by dividing by 128

                bit<8> calc = 3;       //TODO


                if (calc == 1) {
                    // Case 1: 100% qdepth, 0% cpu
                    new_state = stored_q_depth;
                } else if (calc == 2) {
                    // Case 2: 50% qdepth, 50% cpu
                    new_state = (stored_q_depth >> 1) + (stored_cpu >> 1);
                } else if (calc == 3) {
                    // Case 3: 80% qdepth, 20% qdepth
                    // stored_q_depth * 4 / 5 = (stored_q_depth << 2) / 5;
                    new_state = ((stored_q_depth << 2) + stored_q_depth) >> 3;
                    // stored_cpu * 1 / 5 = (stored_cpu) / 5
                    new_state = new_state + (stored_cpu >> 2);  // 20% cpu
                } else if (calc == 4) {
                    // Case 4: 20% qdepth,  80% cpu
                    new_state = (stored_q_depth >> 2);
                    // stored_cpu * 4 / 5 = (stored_cpu << 2) / 5
                    new_state = new_state + ((stored_cpu << 2) + stored_cpu) >> 3;
                } else {
                    // 90% qdepth, 10% cpu
                    // stored_q_depth * 9 / 10 = (stored_q_depth << 3) / 10 + (stored_q_depth << 1) / 10
                    new_state = ((stored_q_depth << 3) + (stored_q_depth << 1)) >> 3;

                    // stored_cpu * 1 / 10 = stored_cpu / 10
                    new_state = new_state + (stored_cpu >> 3);
                }


                if (new_state < 25){
                    new_state = 25;
                } else if(new_state < 50){
                    new_state = 50;
                } else if(new_state < 70){
                    new_state = 70;
                } else if(new_state < 90){
                    new_state = 90;
                } else{
                    new_state = 100;
                }

                //6. Check the WeightTable
                meta.current_path_weight = new_state;
                weight_table.apply();

                //7. Update WCMPTable (registers)
                //meta.path_weight has the new path weight value

                bit<32> total_weights = 0;
                bit<32> current_path_id = 0;
                bit<32> current_path_weight = 0;
                bit<32> faixa_anterior = 0;
                bit<32> peso_anterior = 0;
                bit<32> range0_value = 0;
                bit<32> range1_value = 0;
                bit<32> range2_value = 0;
                bit<32> range3_value = 0;
                bit<32> range4_value = 0;
                bit<32> range5_value = 0;

                meta.path_weight = 3;


                weight0.read(current_path_id, 0);
                if(current_path_id > 0) {
                    range0.read(current_path_weight, 0);

                    peso_anterior = current_path_weight - faixa_anterior;
                    faixa_anterior = current_path_weight;

                    if(current_path_id == meta.path_id){
                        current_path_weight = meta.path_weight;
                    } else{
                        current_path_weight = peso_anterior;
                    }
                    total_weights = total_weights + current_path_weight;
                    range0_value = total_weights;
        			//range0.write(0, total_weights);
                }

                weight1.read(current_path_id, 0);
                if(current_path_id > 0) {
        			range1.read(current_path_weight, 0);

                    peso_anterior = current_path_weight - faixa_anterior;
                    faixa_anterior = current_path_weight;

                    if(current_path_id == meta.path_id){
                        current_path_weight = meta.path_weight;
                    } else{
                        current_path_weight = peso_anterior;
                    }

                    total_weights = total_weights + current_path_weight;
        			//range1.write(0, total_weights);
                    range1_value = total_weights;
                }

                weight2.read(current_path_id, 0);
                if(current_path_id > 0) {
                    range2.read(current_path_weight, 0);

                    peso_anterior = current_path_weight - faixa_anterior;
                    faixa_anterior = current_path_weight;

                    if(current_path_id == meta.path_id){
                        current_path_weight = meta.path_weight;
                    } else{
                        current_path_weight = peso_anterior;
                    }

                    total_weights = total_weights + current_path_weight;
        			//range2.write(0, total_weights);
                    range2_value = total_weights;
                }

                weight3.read(current_path_id, 0);
                if(current_path_id > 0) {
        			range3.read(current_path_weight, 0);
                    peso_anterior = current_path_weight - faixa_anterior;
                    faixa_anterior = current_path_weight;
                    if(current_path_id == meta.path_id){
                        current_path_weight = meta.path_weight;
                    } else{
                        current_path_weight = peso_anterior;
                    }
                    total_weights = total_weights + current_path_weight;
        			//range3.write(0, total_weights);
                    range3_value = total_weights;
                }

                weight4.read(current_path_id, 0);
                if(current_path_id > 0) {
        			range4.read(current_path_weight, 0);
                    peso_anterior = current_path_weight - faixa_anterior;
                    faixa_anterior = current_path_weight;
                    if(current_path_id == meta.path_id){
                        current_path_weight = meta.path_weight;
                    } else{
                        current_path_weight = peso_anterior;
                    }
                    total_weights = total_weights + current_path_weight;
        			//range4.write(0, total_weights);
                    range4_value = total_weights;
                }

                weight5.read(current_path_id, 0);
                if(current_path_id > 0) {
        			range5.read(current_path_weight, 0);
                    peso_anterior = current_path_weight - faixa_anterior;
                    faixa_anterior = current_path_weight;
                    if(current_path_id == meta.path_id){
                        current_path_weight = meta.path_weight;
                    } else{
                        current_path_weight = peso_anterior;
                    }
                    total_weights = total_weights + current_path_weight;
        			//range5.write(0, total_weights);
                    range5_value = total_weights;
                }

    			sumWeight.write(0, total_weights);
                range0.write(0, range0_value);
                range1.write(0, range1_value);
                range2.write(0, range2_value);
                range3.write(0, range3_value);
                range4.write(0, range4_value);
                range5.write(0, range5_value);

                //8. Updates the time of the last weight update
                last_time = standard_metadata.ingress_global_timestamp;
                //last_path_weight_atz.write(meta.path_id, last_time);
                last_path_weight_atz.write(0, last_time);


                log_msg("meta.path_id={}", {meta.path_id});
                log_msg("new_state={}", {new_state});
                log_msg("total_weights={}", {total_weights});

            }
        }

        //**********************************************************************

        /*
          1 - Identificar o id do fluxo do pacote usando hash()
	  	  2 - Verificar o BloomFilter pra saber se é um novo fluxo ou não
	  	  3 - Se não for novo, consultar a ConnTable para buscar o path do fluxo
          4 - Se for novo, gerar um hash do pacote, entre 0 e o índice da WCMPTable
          5 - Retornar o path do indice do hash calculado
          6 - Usar esse caminho para destinar os pacotes desse fluxo
          7 - Atualizar ConnTable
          8 - Atualizar BloomFilter
        */

		if(!hdr.LB_path.isValid() && meta.sw_direction == 0) {
            //primeiro switch conectado ao cliente

			//get flow id's
			//compute_hashes();
            if(hdr.tcp.isValid()){
                compute_hashes(hdr.ipv4.srcAddr, hdr.tcp.srcPort, hdr.tcp.dstPort);
            }
            if(hdr.udp.isValid()){
                compute_hashes(hdr.ipv4.srcAddr, hdr.udp.srcPort, hdr.udp.dstPort);
            }

			//check if it is in the bloom filter
			bloom_filter_1.read(reg_val_one, reg_pos_one);
			bloom_filter_2.read(reg_val_two, reg_pos_two);

            reg_val_one = 0;    //TODO

			// if both entries are set, it is an existing flow
			if (reg_val_one != 1 || reg_val_two != 1) {
				//new flow, update the bloom filter and add the new flow
				bloom_filter_1.write(reg_pos_one, 1);
				bloom_filter_2.write(reg_pos_two, 1);

                set_LB_path_header();

				sumWeight.read(meta.total_weights, 0);

				//path_select(1, meta.total_weights); 	//LOAD BALANCING DECISION
                if(hdr.tcp.isValid()) {
                    path_select_tcp(1, meta.total_weights);
                }else {
                    path_select_udp(1, meta.total_weights);
                }

				bit<32> range_value;

				range0.read(range_value, 0);
				if(meta.path_index_id <= range_value) {
                    weight0.read(meta.path_id, 0);
				} else {
					range1.read(range_value, 0);
					if(meta.path_index_id <= range_value) {
                        weight1.read(meta.path_id, 0);
					} else {
						range2.read(range_value, 0);
						if(meta.path_index_id <= range_value) {
							weight2.read(meta.path_id, 0);
						} else {
							range3.read(range_value, 0);
							if(meta.path_index_id <= range_value) {
								weight3.read(meta.path_id, 0);
							} else {
								range4.read(range_value, 0);
								if(meta.path_index_id <= range_value) {
									weight4.read(meta.path_id, 0);
								} else {
									range5.read(range_value, 0);
									//if(meta.path_index_id <= range_value) {
									weight5.read(meta.path_id, 0);
									//}
								}
							}
						}
					}
				}

	            hdr.LB_path.path_id = meta.path_id;

    		    //path_table.apply(); //seta a porta de saída

                if(hdr.tcp.isValid()){
                    get_flow_id(hdr.ipv4.srcAddr, hdr.tcp.srcPort, hdr.tcp.dstPort);
                }
                if(hdr.udp.isValid()){
                    compute_hashes(hdr.ipv4.srcAddr, hdr.udp.srcPort, hdr.udp.dstPort);
                }

                ConnTable.write(reg_pos_ConnTable, meta.path_id);
    		} else {
    			//existing flow
                if(hdr.tcp.isValid()) {
                    get_flow_id(hdr.ipv4.srcAddr, hdr.tcp.srcPort, hdr.tcp.dstPort);
                }
                if(hdr.udp.isValid()) {
                    get_flow_id(hdr.ipv4.srcAddr, hdr.udp.srcPort, hdr.udp.dstPort);
                }

                ConnTable.read(meta.path_id, reg_pos_ConnTable);

                set_LB_path_header();

                hdr.LB_path.path_id = meta.path_id;
    		}

            //na ida troca o dstAddr
            dnat_table.apply();
    	}

        if(!hdr.LB_path.isValid() && meta.sw_direction == 1) {
            //switch conectado ao servidor

            //if(hdr.rpc.isValid()) {
            //    meta.path_id = hdr.rpc.seq;
            //} else {

                if(hdr.tcp.isValid()) {
                    get_flow_id(hdr.ipv4.dstAddr, hdr.tcp.dstPort, hdr.tcp.srcPort);
                }
                if(hdr.udp.isValid()) {
                    get_flow_id(hdr.ipv4.dstAddr, hdr.udp.dstPort, hdr.udp.srcPort);
                }

                ConnTable.read(meta.path_id, reg_pos_ConnTable);
            //}
            set_LB_path_header();

            hdr.LB_path.path_id = meta.path_id;
      }

      if(hdr.LB_path.isValid() && hdr.LB_path.direction == 0) {
            meta.path_id = hdr.LB_path.path_id;
            if(hdr.tcp.isValid()) {
                get_flow_id(hdr.ipv4.srcAddr, hdr.tcp.srcPort, hdr.tcp.dstPort);
            }
            if(hdr.udp.isValid()) {
                get_flow_id(hdr.ipv4.srcAddr, hdr.udp.srcPort, hdr.udp.dstPort);
            }

            ConnTable.write(reg_pos_ConnTable, meta.path_id);
      }

      path_table.apply(); //seta a porta de saída


      //last hop before server. Remove LB header
      if(meta.sw_direction == 1 && hdr.LB_path.isValid() && hdr.LB_path.direction == 0){

          log_msg("hdr.LB_path.proto_id={}", {hdr.LB_path.proto_id});

          //if(hdr.rpc.isValid()) {
        //      hdr.rpc.seq = hdr.LB_path.path_id;
          //}

          hdr.ethernet.etherType = hdr.LB_path.proto_id;    //TYPE_INT_HEADER;
          hdr.LB_path.setInvalid();
      }

      //set mac addres
      log_msg("hdr.ipv4={}", {hdr.ipv4});
      ipv4_lpm.apply();

      last_INT_timestamp.read(meta.last_INT_timestamp, (bit<32>)meta.egress_port);
      tot_packets.read(meta.tot_packets, (bit<32>)meta.egress_port);

      if((meta.freq_collect_INT == 0 || (standard_metadata.ingress_global_timestamp - meta.last_INT_timestamp >= meta.freq_collect_INT && meta.freq_collect_INT > 0)) && hdr.rpc.isValid() && meta.q_traces < MAX_HOPS) {
          meta.add_INT = 1;
          last_INT_timestamp.write((bit<32>)meta.egress_port, standard_metadata.ingress_global_timestamp);
          tot_packets.write((bit<32>)meta.egress_port, 0);
      } else {
            meta.add_INT = 0;
            last_INT_timestamp.write((bit<32>)meta.egress_port, standard_metadata.ingress_global_timestamp);  //TODO
        }

        meta.ingress_port = standard_metadata.ingress_port;
        meta.egress_port = standard_metadata.egress_spec;

        if( (hdr.int_header.isValid() || meta.add_INT == 1) && meta.lastHop == 1) {
            clone_preserving_field_list(CloneType.I2E, 500, 1);
        }

        meta.tot_packets = meta.tot_packets + 1;
        tot_packets.write((bit<32>)meta.egress_port, meta.tot_packets);

        qtd_drops.read(meta.qtd_drops, 0);

        if(standard_metadata.egress_spec == DROP_PORT || standard_metadata.egress_spec == 0 ){
            meta.qtd_drops = meta.qtd_drops + 1;
            qtd_drops.write(0, meta.qtd_drops);
        }

    }
}

/*************************************************************************
****************  E G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyEgress(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t standard_metadata) {

	action add_int_header() {
        hdr.int_header.setValid();
        hdr.int_header.q_traces = 0;
        hdr.LB_path.proto_id = TYPE_INT_HEADER;
        //hdr.ethernet.etherType = TYPE_INT_HEADER;
    }

    action add_int_trace() {

    	  //TODO MTU check
        hdr.int_trace.push_front(1);
        hdr.int_trace[0].setValid();

        //bit<32> swid = meta.sw_id;
        bit<8> swid = meta.sw_id;
        log_msg("swid={}", {swid});


        #if COLLECT_SIZE == 0
            hdr.int_trace[0].swid           = swid;
            hdr.int_trace[0].q_delay        = (bit <48>) standard_metadata.deq_timedelta;// (standard_metadata.egress_global_timestamp - standard_metadata.ingress_global_timestamp); //microseconds
            hdr.int_trace[0].q_depth        = (bit<24>) standard_metadata.deq_qdepth; // the depth of the queue when the packet was first enqueued, in units of number of packets
            hdr.int_trace[0].q_drops        = meta.qtd_drops;
            hdr.int_trace[0].next_proto     = TYPE_INT_TRACE;
        #else
          #if COLLECT_SIZE == 1
              hdr.int_trace[0].swid           = (bit <32>)swid;
              hdr.int_trace[0].enq_qdepth     = standard_metadata.enq_qdepth;
              hdr.int_trace[0].padding        = 0;
              hdr.int_trace[0].next_proto     = TYPE_INT_TRACE;

          #else
            #if COLLECT_SIZE == 2
                  hdr.int_trace[0].swid           = swid;
                  hdr.int_trace[0].ingress_port   = meta.ingress_port;
                  hdr.int_trace[0].egress_port    = meta.egress_port;
                  hdr.int_trace[0].enq_timestamp  = standard_metadata.enq_timestamp;
                  hdr.int_trace[0].enq_qdepth     = standard_metadata.enq_qdepth;
                  hdr.int_trace[0].deq_timedelta  = standard_metadata.deq_timedelta;
                  hdr.int_trace[0].deq_qdepth     = standard_metadata.deq_qdepth;
                  hdr.int_trace[0].ingress_timestamp = (bit <48>) standard_metadata.ingress_global_timestamp;
                  hdr.int_trace[0].egress_timestamp = (bit <48>) standard_metadata.egress_global_timestamp;
                  hdr.int_trace[0].qtd_drops      = meta.qtd_drops;
                  hdr.int_trace[0].next_proto     = TYPE_INT_TRACE;

            #else
              #if COLLECT_SIZE == 3
                  hdr.int_trace[0].swid           = swid;
                  hdr.int_trace[0].ingress_port   = meta.ingress_port;
                  hdr.int_trace[0].egress_port    = meta.egress_port; //standard_metadata.egress_port;
                  hdr.int_trace[0].enq_timestamp  = standard_metadata.enq_timestamp;
                  hdr.int_trace[0].enq_qdepth     = standard_metadata.enq_qdepth;
                  hdr.int_trace[0].deq_timedelta  = standard_metadata.deq_timedelta;
                  hdr.int_trace[0].deq_qdepth     = standard_metadata.deq_qdepth;
                  hdr.int_trace[0].ingress_timestamp = (bit <48>) standard_metadata.ingress_timestamp;
                  hdr.int_trace[0].egress_timestamp = (bit <48>) standard_metadata.egress_global_timestamp;
                  hdr.int_trace[0].int_field_1    = (bit <64>) standard_metadata.packet_length;
                  hdr.int_trace[0].int_field_2    = (bit <64>) (standard_metadata.egress_global_timestamp - meta.ingress_timestamp);
                  hdr.int_trace[0].int_field_3    = 0;
                  hdr.int_trace[0].int_field_4    = (bit <64>)meta.tot_packets;
                  hdr.int_trace[0].int_field_5    = meta.last_INT_timestamp;
                  hdr.int_trace[0].int_field_6    = 0;
                  hdr.int_trace[0].next_proto     = TYPE_INT_TRACE;
              #else
                  hdr.int_trace[0].swid           = (bit <8>) swid;
                  hdr.int_trace[0].ingress_port   = meta.ingress_port;
                  hdr.int_trace[0].egress_port    = meta.egress_port;
                  hdr.int_trace[0].enq_timestamp  = meta.enq_timestamp;
                  hdr.int_trace[0].enq_qdepth     = 1; //meta.enq_qdepth;
                  hdr.int_trace[0].deq_timedelta  = meta.deq_timedelta;
                  hdr.int_trace[0].deq_qdepth     = 2; //meta.deq_qdepth;
                  hdr.int_trace[0].int_field_1    = 3; // standard_metadata.packet_length;
                  hdr.int_trace[0].int_field_2    = 0; //standard_metadata.egress_global_timestamp - meta.ingress_timestamp;
                  hdr.int_trace[0].int_field_3    = 0;
                  hdr.int_trace[0].int_field_4    = 0;
                  hdr.int_trace[0].int_field_5    = meta.last_INT_timestamp;
                  hdr.int_trace[0].int_field_6    = 0;
                  hdr.int_trace[0].next_proto     = TYPE_INT_TRACE;
              #endif
            #endif
          #endif
        #endif

        hdr.int_header.q_traces = hdr.int_header.q_traces + 1;
        meta.qtd_drops = 0;
    }

    action remove_headers() {
        log_msg("standard_metadata.packet_length={}", {standard_metadata.packet_length});

        hdr.packet_in.setValid();
        hdr.packet_in.sw_id = (bit<32>) meta.sw_id;

        //hdr.ethernet.setInvalid();
        //hdr.ethernet.etherType = TYPE_INT_HEADER;
        //hdr.LB_path.setInvalid();
        //hdr.ipv4.setInvalid();
        //hdr.udp.setInvalid();
        //hdr.tcp.setInvalid();
        //hdr.rpc.setInvalid();
    }

    action send_INT_to_Controller() {

    	//add cabeçalho packet_in (sw_id, + metrics)

      //log_msg("hdr.int_header.q_traces={}", {hdr.int_header.q_traces});
      //log_msg("standard_metadata.packet_length={}", {standard_metadata.packet_length});

        //calcular o tamanho do pacote (tam 52 com 3 int_trace)
        meta.packet_size = SIZE_PKT_IN + SIZE_ETHERNET + SIZE_LB_PATH + SIZE_INT_HEADER + (SIZE_INT_TRACE * hdr.int_header.q_traces);

        if(hdr.int_host.isValid()){
          meta.packet_size = meta.packet_size + SIZE_INT_HOST;
        }

        //log_msg("meta.packet_size={}", {meta.packet_size});

		/*
        hdr.ethernet.dstAddr = dstAddr;
        hdr.ethernet.srcAddr = hdr.ethernet.dstAddr;
        hdr.ethernet.dstAddr = dstAddr;
        hdr.ipv4.ttl         = 64;
        hdr.ipv4.dstAddr     = ip_dstAddr;
		*/
        //Remove payload
        truncate(meta.packet_size);

        remove_headers();
    }

    action remove_INT() {
        hdr.int_trace.pop_front(MAX_HOPS);
        //hdr.int_header.q_traces=0;

        hdr.int_header.setInvalid();

        hdr.int_host.setInvalid();
        hdr.ethernet.etherType = TYPE_IPV4;
    }

    apply {

    	if (hdr.ipv4.isValid()) {

            if(meta.add_INT == 1) {

                  if(!hdr.int_header.isValid()) {
                      add_int_header();
                  }

                  //int_trace.apply();
                  add_int_trace();

                  if(hdr.int_header.isValid() && hdr.int_header.q_traces == 1) {
                    hdr.int_trace[0].next_proto     = TYPE_IPV4;
                  }

            }

            if(standard_metadata.instance_type == PKT_INSTANCE_TYPE_NORMAL && meta.lastHop == 1 && hdr.int_header.isValid() ) {
                remove_INT();
            } else if(standard_metadata.instance_type == PKT_INSTANCE_TYPE_INGRESS_CLONE) {
				        send_INT_to_Controller();
                //t_forward_int.apply();
            }


            if(meta.lastHop == 1 && hdr.LB_path.isValid()){
            	hdr.ethernet.etherType = TYPE_IPV4;
            	hdr.LB_path.setInvalid();
            }

            //qtd_drops.write(0, meta.qtd_drops);//drops desde a ultima coleta

        }

    }
}

/*************************************************************************
*************   C H E C K S U M    C O M P U T A T I O N   **************
*************************************************************************/

control MyComputeChecksum(inout headers  hdr, inout metadata meta) {
     apply {
        update_checksum(
        hdr.ipv4.isValid(),
            { hdr.ipv4.version,
              hdr.ipv4.ihl,
              hdr.ipv4.diffserv,
              hdr.ipv4.totalLen,
              hdr.ipv4.identification,
              hdr.ipv4.flags,
              hdr.ipv4.fragOffset,
              hdr.ipv4.ttl,
              hdr.ipv4.protocol,
              hdr.ipv4.srcAddr,
              hdr.ipv4.dstAddr },
            hdr.ipv4.hdrChecksum,
            HashAlgorithm.csum16);

        update_checksum_with_payload(
            meta.alt_srcAddr == 1 && hdr.tcp.isValid(),
            {
                hdr.ipv4.srcAddr,
                hdr.ipv4.dstAddr,
                8w0,
                hdr.ipv4.protocol,
                meta.tcp_segment_len,
                hdr.tcp.srcPort,
                hdr.tcp.dstPort,
                hdr.tcp.seqNo,
                hdr.tcp.ackNo,
                hdr.tcp.dataOffset,
                hdr.tcp.res,
                hdr.tcp.flags,
                hdr.tcp.window,
                hdr.tcp.urgentPtr,
                hdr.rpc
            },
            hdr.tcp.checksum,
            HashAlgorithm.csum16
        );

        update_checksum_with_payload(
            meta.alt_srcAddr == 1 && hdr.udp.isValid(),
            {
                hdr.ipv4.srcAddr,
                hdr.ipv4.dstAddr,
                8w0,                     // Zero padding
                hdr.ipv4.protocol,       // Protocol (UDP is 17)
                hdr.udp.length_,          // UDP length
                hdr.udp.srcPort,         // Source port
                hdr.udp.dstPort,         // Destination port
                hdr.udp.length_,          // Length field from UDP header
                16w0,
                hdr.rpc
                //hdr.udp.checksum         // Checksum field in UDP header
                //hdr.payload              // Optional: Add UDP payload if needed
            },
            hdr.udp.checksum,            // Field to store the computed checksum
            HashAlgorithm.csum16          // 16-bit one's complement checksum
        );
    }
}

/*************************************************************************
***********************  D E P A R S E R  *******************************
*************************************************************************/

control MyDeparser(packet_out packet, in headers hdr) {
    apply {
        packet.emit(hdr.packet_in); //pkt send to the controller
        packet.emit(hdr.ethernet);
        packet.emit(hdr.LB_path);
        packet.emit(hdr.int_header);
        packet.emit(hdr.int_trace);
        packet.emit(hdr.int_host);
        packet.emit(hdr.ipv4);
        packet.emit(hdr.udp);
        packet.emit(hdr.tcp);
        packet.emit(hdr.rpc);
    }
}

/*************************************************************************
***********************  S W I T C H  *******************************
*************************************************************************/

V1Switch(
MyParser(),
MyVerifyChecksum(),
MyIngress(),
MyEgress(),
MyComputeChecksum(),
MyDeparser()
) main;
