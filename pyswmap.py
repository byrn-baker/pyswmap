#!/usr/bin/python3

# There is still a great deal of work required on this module.  Please
# use with caution.  
# -Jordan 

import sys
from ipaddress import (
        IPv6Address,
        IPv6Network,
        ip_network,
        ip_address,
        )
from math import (
        log,
        )

class MapCalc(object):

    def __init__(self,**bmr):
        #rulev6,rulev4):
        self.portranges = False

        # Validate and set BMR and BMR derived values 
        self._check_bmr_values(bmr)

    def _check_bmr_values(self,bmr):
        # Assume these values have not been supplied.  Validate later.
        self.ealen = False
        self.ratio = False

        # Validate that a proper PSID Offset has been set
        if 'psidoffset' not in bmr:
            print("The PSID offset has not been set")
            sys.exit(1)
        else:
            self.psidoffset = self._psid_offset(bmr['psidoffset'])

        # Validate that a proper IPv4 rule prefix is defined
        if 'rulev4' not in bmr:
            print("The rule IPv4 prefix has not been set")
            sys.exit(1)
        else:
            self.rulev4 = self._ipv4_rule(bmr['rulev4'])

        # Validate that a proper IPv6 rule prefix is defined
        if 'rulev6' not in bmr:
            print("The rule IPv6 prefix has not been set")
            sys.exit(1)
        else:
            self.rulev6 = self._ipv6_rule(bmr['rulev6'])

        # Check if EA length was passed
        if 'ealen' not in bmr:
            self.ealen = False
        else:
            self.ealen = bmr['ealen']
            self.ratio = self._calc_ratio(bmr['ealen'])

        # Check if sharing ratio was passed or calculated by _calc_ratio
        if 'ratio' not in bmr:
            # Skip if we have already calculated ratio
            if not (self.ratio):
                self.ratio = False
        else:
            if (self.ealen):
                # Check to see if supplied EA length contradicts supplied ratio
                if ( bmr['ratio'] != self.ratio ):
                    eavalue = "EA value {}".format(self.ealen)
                    sharingratio = "sharing ratio {}".format(bmr['ratio'])
                    print("Supplied {} and {} are contradictory".format(
                                                                  eavalue,
                                                                  sharingratio)
                         )
                    sys.exit(1)
            else:
                self.ratio = bmr['ratio']
                self.ealen = self._calc_ea(bmr['ratio'])

        # EA length or sharing ratio must be set
        if not ( self.ealen or self.ratio):
            print("The BMR must include an EA length or sharing ratio")
            sys.exit(1)

        # Since we have not hit an exception we can calculate the port bits
        self.portbits = self._calc_port_bits()

    def _ipv4_rule(self,rulev4):
        try:
            self.rulev4mask = ip_network(
                        rulev4,
                        strict=False
                        ).prefixlen
        except ValueError: 
            print("Invalid IPv4 prefix {}".format(rulev4))
            sys.exit(1)

        return rulev4

    def _ipv6_rule(self,rulev6):
        try:
            self.rulev6mask = IPv6Network(
                        rulev6,
                        strict=False
                        ).prefixlen
        except ValueError:
            print("Invalid IPv6 prefix {}".format(rulev6))
            sys.exit(1)

        return rulev6

    def _psid_offset(self,psidoffset):
        PSIDOFFSET_MAX = 6
        if psidoffset in range(0,PSIDOFFSET_MAX+1):
            return psidoffset
        else:
            print("Invalid PSID Offset value: {}".format(psidoffset))
            sys.exit(1)

    def _psid_range(self,x):
        rset = []
        for i in range(0,x+1):
            rset.append(2**i)
        return rset

    def _calc_port_bits(self):
        portbits = 16 - self.psidoffset - self.psidbits
        return portbits

    def _calc_ea(self,ratio):
        if ratio not in ( self._psid_range(16) ):
            sys.exit(1)

        if ( 1 == ratio):
            self.psidbits = 0
        else:
            self.psidbits = int(log(ratio,2))
        ealen = self.psidbits + ( 32 - self.rulev4mask )
        return ealen

    def _calc_ratio(self,ealen):
        self.psidbits = ealen - ( 32 - self.rulev4mask )
        ratio = 2**self.psidbits
        return ratio

    def gen_psid(self,portnum):
        if ( portnum < self.start_port() ):
            print("port value is less than allowed by PSID Offset")
            sys.exit(1)
        self.psid = (portnum & ((2**self.psidbits - 1) << self.portbits)) 
        self.psid = self.psid >> self.portbits
        return self.psid

    def port_ranges(self):
        return 2**self.psidoffset - 1

    def start_port(self):
        if self.psidoffset == 0: return 0  
        return 2**(16 - self.psidoffset)

    def port_list(self):
        startrange = self.psid * (2**self.portbits) + self.start_port()
        increment = (2**self.psidbits) * (2**self.portbits)
        portlist = [ ]
        for port in range(startrange,startrange + 2**self.portbits):
            if port >= 65536: continue
            portlist.append(port)
        for x in range(1,self.port_ranges()):
            startrange += increment
            for port in range(startrange,startrange + 2**self.portbits):
                portlist.append(port)
        self.portlist = portlist
        return portlist

    def ipv4_index(self,ipv4addr):
        if ip_address(ipv4addr) in ip_network(self.rulev4):
            x = ip_address(ipv4addr)
            y = ip_network(self.rulev4,strict=False).network_address
            self.ipv4addr = x
            return ( int(x) - int(y) )
        else:
            print("Error: IPv4 address {} not in Rule IPv4 subnet {}".format(
                  ipv4add,
                  ip_network(self.rulev4,strict=False).network_address))
            sys.exit(1)

    def gen_mapaddr(self,ipv4index):
        addroffset = 128 - (self.rulev6mask + ( self.ealen - self.psidbits))
        psidshift = 128 - ( self.rulev6mask + self.ealen )
        mapaddr = IPv6Network(self.rulev6,strict=False).network_address
        mapaddr = int(mapaddr) | ( ipv4index << addroffset )
        mapaddr = mapaddr | ( self.psid << psidshift)
        self.pd = "{}/{}".format(
                                   IPv6Address(mapaddr),
                                   self.rulev6mask + self.ealen
                                )
        mapce = mapaddr | ( int(self.ipv4addr) << 16 )
        mapce = mapce | self.psid
        self.mapce = "{}".format(IPv6Address(mapce))

if __name__ == "__main__":
    # A quick example showing current module capabilities:
    # The next four lines are used to supply the BMR
    # 1.  The IPv6 rule prefix: rulev6      (a string) 
    # 2.  The IPv4 rule prefix: rulev4      (a string)
    # 3.  The PSID Offset:      psidoffset  (an integer)
    #
    # One of the two following values:
    # 4a. The Sharing Ratio:    ratio       (an integer)
    #                    or
    # 4b. The EA Length:        ealen       (an integer)
    # 
    m = MapCalc( rulev6='fd80::/48',
                 rulev4='24.50.100.0/24',
                 psidoffset=6,
                 ratio=64,
                 #ealen=14,
               )

    # Supply arbitrary layer-4 port that is valid given PSID Offset used
    # to calculate the PSID.  PSID is stored in m.psid
    portvalue = 40000
    m.gen_psid(portvalue)

    # Supply an IPv4 address from IPv4 rule prefix and use it and the 
    # PSID calculated in the previous statement to generate the MAP CE
    # address and parent PD.  We must first feed it to the ipv4_index()
    # method in order to get the integer index value for the IPv4 address.
    sharedv4 = "24.50.100.100"
    m.gen_mapaddr(m.ipv4_index(sharedv4))

    # Print out some of the pertinent user supplied and calculated values
    print("\n\n")
    print("################################################")
    print("BMR:")
    print("    Rule IPv6 Prefix: {}".format(m.rulev6))
    print("    Rule IPv4 Prefix: {}".format(m.rulev4))
    print("    PSID Offset:      {}".format(m.psidoffset))
    print("    Sharing Ratio:    {} to 1".format(m.ratio))
    print("    EA Length:        {}".format(m.ealen))
    print("Shared IPv4 and Port Session State:")
    print("    Shared IPv4:      {}".format(sharedv4))
    print("    Port:             {}".format(portvalue))
    print("Other Calculated Values:")
    print("    Port Bits:        {}".format(m.portbits))
    print("    Ranges Allocated: {}".format(2**m.psidoffset - 1))
    print("    PSID Bits:        {}".format(m.psidbits))
    print("################################################")
    print("------------------------------------------------")
    print("PSID: {}".format(m.psid))
    print("PD for this client is: {}".format(m.pd))
    print("MAP CE Address is: {}".format(m.mapce))
    print("------------------------------------------------")
    print("Output to follow will include the full range of ports assigned")
    print("to calculated PSID.")
    print("Note: This can result in a really long list up to 2^16")
    raw_input = vars(__builtins__).get('raw_input',input)
    raw_input("Press the ENTER/RETURN key to continue")
    print("\n")
    print(m.port_list())
