
h5 xterm -e "gcc -o pkt_gen/udp_server pkt_gen/server.c -lpthread -lbpf"
h1 xterm -e "gcc -o pkt_gen/udp_client pkt_gen/client.c -lpthread"

h5 xterm -e "python3 eBPF/eBPF_load.py 1 0"
h6 xterm -e "python3 eBPF/eBPF_load.py 1 0"
sh echo “attach eBPF programs” &
sh sleep 4

h5 xterm -title "h5 server" -e "./pkt_gen/udp_server 5" &
h6 xterm -title "h6 server" -e "./pkt_gen/udp_server 6" &
sh sleep 5 &
h1 xterm -title "h1 send" -e "./pkt_gen/udp_client h1.csv " &
h2 xterm -title "h2 send" -e "./pkt_gen/udp_client h2.csv "


sh echo “test completed”
sh sleep 20
sh sudo killall xterm

sh echo “detach eBPF programs”

h5 xterm -e "python3 eBPF/eBPF_load.py 2 0" &
h6 xterm -e "python3 eBPF/eBPF_load.py 2 0" &
sh sleep 1
