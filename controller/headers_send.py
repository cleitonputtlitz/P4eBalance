from scapy.all import *
import sys, os


class packet_out_header(Packet):
    fields_desc = [ BitField("total_paths", 0, 8) ]


class active_path(Packet):
    fields_desc = [ BitField("path_id", 0, 32),
                    BitField("path_weight", 0, 32),
                  ]

class packet_in_header(Packet):
    fields_desc = [ BitField("sw_id", 0, 32) ]



bind_layers(packet_out_header, active_path)
bind_layers(active_path, active_path)
