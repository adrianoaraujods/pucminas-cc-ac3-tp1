/*
 * Microbenchmark sintetico (Fase 7 / Etapa 3 - frente de desempenho):
 * padrao *scan* para contrastar LRU x SRRIP.
 *
 * Um buffer B com o tamanho da LLC (2 MiB) e varrido em streaming; entre
 * passadas, um hot set H (32 KiB, cabecario da L1) e revisitado. No LRU o
 * streaming recicla a L2/LLC (thrash do hot set); no SRRIP (L2+LLC) as
 * linhas do streaming entram em "long distance" e o hot set preserva
 * RRPV=0 => mais hits em L2/LLC, maior IPC.
 *
 * O custo e limitado pelo simulador via --maxinsts (config_channel.py).
 *
 * Uso: scan [n_passes]
 */

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#define BSZ (unsigned)(2u * 1024 * 1024) /* = tamanho da LLC */
#define HSZ (unsigned)(32u * 1024)       /* = tamanho da L1 */

int main(int argc, char **argv)
{
    int passes = argc > 1 ? atoi(argv[1]) : 256;
    volatile unsigned char *B = aligned_alloc(4096, BSZ);
    volatile unsigned char *H = aligned_alloc(4096, HSZ);
    if (!B || !H)
        return 1;

    unsigned long acc = 0;
    for (volatile unsigned char *p = B; p < B + BSZ; p += 64)
        acc += *p;
    for (volatile unsigned char *p = H; p < H + HSZ; p += 64)
        acc += *p;

    for (int it = 0; it < passes; it++) {
        for (volatile unsigned char *p = B; p < B + BSZ; p += 64)
            acc += *p;
        for (volatile unsigned char *p = H; p < H + HSZ; p += 64)
            acc += *p;
    }
    printf("scan acc=%lu (passes=%d)\n", acc, passes);
    return 0;
}