#!/usr/bin/env python3
import os
import random
import sys
import shutil
import logging
import json
import time
import argparse
from decimal import *
from pdb import set_trace
from .test_framework.authproxy import AuthServiceProxy, JSONRPCException
from .blocksigning import BlockSigning
from .hsm import HsmPkcs11
from .connectivity import getelementsd, loadConfig

NUM_OF_NODES_DEFAULT = 9
NUM_OF_SIGS_DEFAULT = 6
MESSENGER_TYPE_DEFAULT = "zmq"
IN_RATE = 0
IN_PERIOD = 0
IN_ADDRESS = ""
SCRIPT = ""
PRVKEY = ""

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rpcconnect', required=True, type=str, help="Client RPC host")
    parser.add_argument('--rpcport', required=True, type=str, help="Client RPC port")
    parser.add_argument('--rpcuser', required=True, type=str, help="RPC username for client")
    parser.add_argument('--rpcpassword', required=True, type=str, help="RPC password for client")
    parser.add_argument('--id', required=True, type=int, help="Federation node id")
    parser.add_argument('--msgtype', default=MESSENGER_TYPE_DEFAULT, type=str, help="Messenger type protocol used by federation. 'Kafka' and 'zmq' values supported")
    parser.add_argument('--nodes', default="", type=str, help="Nodes for zmq protocol. Example use 'node0:1503,node1:1502'")

    parser.add_argument('--walletpassphrase', default="", type=str, help="Wallet pass phrase, only required if the nodes wallet is encrypted.")

    parser.add_argument('--nnodes', default=NUM_OF_NODES_DEFAULT, type=int, help="The number of block signing members of the federation, the n parameter in an m-of-n block signing script.")
    parser.add_argument('--nsigs', default=NUM_OF_SIGS_DEFAULT, type=int, help="The number of signatures required for a valid block, the m parameter in an m-of-n block signing script.")
    parser.add_argument('--blocktime', default=60, type=int, help="Target time between blocks, in seconds (default: 60).")
    parser.add_argument('--redeemscript', required=True, type=str, help="Block signing script.")

    parser.add_argument('--inflationrate', default=IN_RATE, type=float, help="Inflation rate. Example 0.0101010101")
    parser.add_argument('--inflationperiod', default=IN_PERIOD, type=int, help="Inflation period (in blocks)")
    parser.add_argument('--inflationaddress', default=IN_ADDRESS, type=str, help="Address for inflation payments")
    parser.add_argument('--reissuancescript', default=SCRIPT, type=str, help="Reissuance token script")
    parser.add_argument('--reissuanceprivkey', default=PRVKEY, type=str, help="Reissuance private key")

    parser.add_argument('--hsm', default=False, type=bool, help="Specify if an HSM will be used for signing blocks")
    return parser.parse_args()

def main():
    args = parse_args()

    logging.basicConfig(
        format='%(asctime)s %(name)s:%(levelname)s:%(process)d: %(message)s',
        level=logging.INFO
    )

    conf = {}
    conf["rpcuser"] = args.rpcuser
    conf["rpcpassword"] = args.rpcpassword
    conf["rpcport"] = args.rpcport
    conf["rpcconnect"] = args.rpcconnect
    conf["id"] = args.id
    conf["msgtype"] = args.msgtype
    conf["walletpassphrase"] = args.walletpassphrase
    conf["nsigs"] = args.nsigs

    conf["blocktime"] = args.blocktime
    conf["redeemscript"] = args.redeemscript

    inrate = args.inflationrate
    inprd = args.inflationperiod
    inaddr = args.inflationaddress
    inscript = args.reissuancescript
    ripk = args.reissuanceprivkey
    conf["reissuanceprivkey"] = ripk

    if args.nodes != "":
        # Provide ip:port for zmq protocol
        nodes = args.nodes.split(',')
    else:
        # Maintain old behavior for Kafka
        nodes = ['']*args.nnodes

    signer = None
    if args.hsm:
        signer = HsmPkcs11(os.environ['KEY_LABEL'])

    signing_node = BlockSigning(conf, nodes, inrate, inprd, inaddr, inscript, signer)
    signing_node.start()

    try:
        while 1:
            if signing_node.stopped():
                signing_node.join()
                raise Exception("Node thread has stopped")
            time.sleep(0.01)
    except KeyboardInterrupt:
        signing_node.stop()
        signing_node.join()

if __name__ == "__main__":
    main()
