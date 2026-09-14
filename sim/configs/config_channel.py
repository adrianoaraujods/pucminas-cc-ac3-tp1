#!/usr/bin/env python3
# Copyright (c) 2026 Grupo AC3
#
# Script de configuracao SE proprio para o experimento do canal encoberto
# baseado em estado de cache (LRU x SRRIP/RRIP).
#
# NOTA (bypass deliberado da gem5 stdlib): a stdlib do gem5
# (gem5.components.cachehierarchies.classic) expoe apenas hierarquias com
# L1+L2 (PrivateL1PrivateL2...), sem LLC classica customizavel, e nao permite
# injetar replacement_policy por cache. O experimento exige (1) tres niveis
# (L1, L2 e LLC) com a LLC como cache classica real e (2) troca de politica
# de substituicao por nivel. Por isso este script usa wiring de baixo nivel
# (SimObject), mantendo o escopo estreito e sem virar interface reutilizavel.

import argparse
import os

import m5
from m5.objects import *


class SmtProcess(Process):
    """SMT com um unico binario: o mesmo Process e referenciado pelos dois
    thread contexts, entao a arvore de simulacao o visita duas vezes durante
    instantiate e chamaria initState() no objeto C++ duas vezes (crash no
    mapeamento duplicado das stacks). Este override executa o initState C++
    apenas uma vez. O padrao da gem5 e um Process por contexto (SE nao cria
    contextos livres para um mesmo binario em um unico core)."""

    _ran_init = False

    def initState(self):
        if not SmtProcess._ran_init:
            SmtProcess._ran_init = True
            self.getCCObject().initState()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=str, required=True,
                        help="caminho do executavel (driver do canal)")
    parser.add_argument("--cmdargs", type=str, default="",
                        help="argumentos repassados ao binary (separados por espaco)")
    parser.add_argument("--cpu-type", type=str, default="timing",
                        choices=["timing", "minor", "o3", "atomic"],
                        help="tipo de CPU")
    parser.add_argument("--policy", type=str, default="lru",
                        choices=["lru", "brrip", "rrrip", "srrrip", "random"],
                        help="politica de substituicao aplicada nas caches de dados")
    parser.add_argument("--policy-scope", type=str, default="all",
                        choices=["all", "l2llc", "llc", "l1"],
                        help="onde aplicar a politica escolhida")
    parser.add_argument("--l1-size", type=str, default="32KiB")
    parser.add_argument("--l1-assoc", type=int, default=8)
    parser.add_argument("--l2-size", type=str, default="256KiB")
    parser.add_argument("--l2-assoc", type=int, default=8)
    parser.add_argument("--llc-size", type=str, default="2MiB")
    parser.add_argument("--llc-assoc", type=int, default=16)
    parser.add_argument("--mem-size", type=str, default="8GiB")
    parser.add_argument("--cpu-clock", type=str, default="2GHz")
    parser.add_argument("--sys-clock", type=str, default="2GHz")
    parser.add_argument("--num-threads", type=int, default=1,
                        help="threads por CPU (1 = sem SMT)")
    parser.add_argument("--num-cores", type=int, default=1,
                        help="nucleos de CPU (compartilham L2/LLC; sem SMT no O3 25.1)")
    parser.add_argument("--maxinsts", type=int, default=0,
                        help="limite de instrucoes simuladas (0 = ilimitado)")
    parser.add_argument("--outdir", type=str, default=os.getcwd(),
                        help="diretorio de saida (stats.txt, config.ini, etc.)")
    return parser.parse_args()


def make_policy(name, scope, level):
    """Nivel: 'l1','l2','llc'."""
    apply = {"all": True, "l1": level == "l1",
             "l2llc": level in ("l2", "llc"), "llc": level == "llc"}
    if not apply[scope]:
        return LRURP()
    if name == "lru":
        return LRURP()
    if name == "brrip":
        return BRRIPRP()
    if name == "rrrip":
        return RRIPRP()
    if name == "srrrip":
        # SRRIP canonico (Jaleel'2010): insercao sempre em 'long' (btp=100),
        # hit -> RRPV=0 (hit_priority=True). Sem codigo C++ novo.
        return BRRIPRP(num_bits=2, btp=100, hit_priority=True)
    if name == "random":
        return RandomRP()
    raise ValueError(name)


def make_l1(name, size, assoc, policy):
    c = Cache()
    c.size = size
    c.assoc = assoc
    c.tag_latency = 2
    c.data_latency = 2
    c.response_latency = 2
    c.mshrs = 4
    c.tgts_per_mshr = 20
    c.write_buffers = 8
    c.replacement_policy = policy
    if name == "l1i":
        c.is_read_only = True
        c.writeback_clean = True
    return c


def make_ll(name, size, assoc, policy, lat):
    c = Cache()
    c.size = size
    c.assoc = assoc
    c.tag_latency = lat
    c.data_latency = lat
    c.response_latency = lat
    c.mshrs = 32
    c.tgts_per_mshr = 12
    c.write_buffers = 16
    c.replacement_policy = policy
    return c


def build_system(args, cpus):
    system = System(cpu=cpus, mem_mode="timing",
                    mem_ranges=[AddrRange(args.mem_size)],
                    cache_line_size=64)

    system.voltage_domain = VoltageDomain()
    system.clk_domain = SrcClockDomain(clock=args.sys_clock,
                                       voltage_domain=system.voltage_domain)
    system.cpu_voltage_domain = VoltageDomain()
    system.cpu_clk_domain = SrcClockDomain(clock=args.cpu_clock,
                                           voltage_domain=system.cpu_voltage_domain)
    for cpu in cpus:
        cpu.clk_domain = system.cpu_clk_domain

    system.membus = SystemXBar()
    system.l2xbar = L2XBar()
    system.llcxbar = L2XBar()

    l2_pol = make_policy(args.policy, args.policy_scope, "l2")
    llc_pol = make_policy(args.policy, args.policy_scope, "llc")

    l2 = make_ll("l2", args.l2_size, args.l2_assoc, l2_pol, lat=20)
    llc = make_ll("llc", args.llc_size, args.llc_assoc, llc_pol, lat=30)

    system.l2 = l2
    system.llc = llc

    for cpu in cpus:
        l1i_pol = LRURP()
        l1d_pol = make_policy(args.policy, args.policy_scope, "l1")
        l1i = make_l1("l1i", args.l1_size, args.l1_assoc, l1i_pol)
        l1d = make_l1("l1d", args.l1_size, args.l1_assoc, l1d_pol)
        cpu.addPrivateSplitL1Caches(l1i, l1d)
        cpu.createInterruptController()
        cpu.connectAllPorts(system.l2xbar.cpu_side_ports,
                            system.membus.cpu_side_ports,
                            system.membus.mem_side_ports)

    l2.cpu_side = system.l2xbar.mem_side_ports
    l2.mem_side = system.llcxbar.cpu_side_ports
    llc.cpu_side = system.llcxbar.mem_side_ports
    llc.mem_side = system.membus.cpu_side_ports

    system.system_port = system.membus.cpu_side_ports

    system.mem_ctrl = MemCtrl()
    system.mem_ctrl.dram = DDR3_1600_8x8()
    system.mem_ctrl.dram.range = system.mem_ranges[0]
    system.mem_ctrl.port = system.membus.mem_side_ports

    return system


def make_cpu(args, cpu_id=0):
    if args.cpu_type == "timing":
        return TimingSimpleCPU(numThreads=args.num_threads, cpu_id=cpu_id)
    if args.cpu_type == "minor":
        return MinorCPU(numThreads=args.num_threads, cpu_id=cpu_id)
    if args.cpu_type == "o3":
        return O3CPU(numThreads=args.num_threads, cpu_id=cpu_id)
    if args.cpu_type == "atomic":
        return AtomicSimpleCPU(numThreads=args.num_threads, cpu_id=cpu_id)
    raise ValueError(args.cpu_type)


def main():
    args = parse_args()

    cpus = [make_cpu(args, i) for i in range(args.num_cores)]

    # SE no gem5 25.1 exige len(workload) == numThreads. Com o mesmo
    # Process nos contextos, o initState C++ rodaria duas vezes (crash no
    # mapRegion das stacks); o override SmtProcess executa initState uma
    # unica vez, que ativa apenas o contexto 0. Os demais contextos ficam
    # Halted e livres para o clone (pthread_create) do proprio binario.
    process = SmtProcess(pid=100) if args.num_threads > 1 else Process(pid=100)
    process.executable = args.binary
    if args.cmdargs:
        process.cmd = [args.binary] + args.cmdargs.split()
    else:
        process.cmd = [args.binary]
    process.cwd = os.getcwd()

    for cpu in cpus:
        if args.num_threads > 1:
            cpu.workload = [process] * args.num_threads
        else:
            cpu.workload = process
        cpu.createThreads()

    binary = os.path.abspath(args.binary)
    system = build_system(args, cpus)
    system.multi_thread = args.num_threads > 1
    system.workload = SEWorkload.init_compatible(binary)

    root = Root(full_system=False, system=system)
    m5.instantiate()

    if args.maxinsts:
        exit_event = m5.simulate(args.maxinsts)
    else:
        exit_event = m5.simulate()
    print(f"Simulation end reached @ tick {m5.curTick()} "
          f"(exit reason: {exit_event.getCause()})")
    m5.stats.dump()


if __name__ == "__m5_main__":
    main()