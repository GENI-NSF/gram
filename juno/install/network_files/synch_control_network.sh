echo 'Post Creation of Gram Networks - need to sync up control and network'
service openvswitch-switch restart
service neutron-plugin-openvswitch-agent restart
service neutron-l3-agent restart
service neutron-dhcp-agent restart
service neutron-metadata-agent restart
sed -i "s/^router_id =.*/router_id = `cat /home/gram/neutron_ext_router`/" /etc/neutron/l3_agent.ini
sed -i "s/^gateway_external_network_id =.*/gateway_external_network_id = `cat /home/gram/neutron_public_net`/" /etc/neutron/l3_agent.ini
