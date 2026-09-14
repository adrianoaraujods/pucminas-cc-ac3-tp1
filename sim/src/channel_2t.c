/*
 * canal encoberto por estado de cache com 2 fios (Algoritmos 1+3,
 * Xiong & Szefer) - SMT no gem5 SE.
 *
 * Modelo: um unico core TimingSimple com numThreads=2 (SMT), L1
 * compartilhada e privada ao core. O O3-SMT do gem5 25.1 pinado
 * segfaulta (Decode::sortInsts) mesmo single-thread, entao o experimento
 * roda com a CPU timing; alem disso, no TimingSimple a latencia de uma
 * miss que extrapola a L1 nao e visivel no caminho load-to-use, logo o
 * unico discriminador util e o par hit/miss dentro da L1 compartilhada:
 * o recurso compartilhado observado e a L1. Isso corresponde ao cenario
 * fisico de co-locacao SMT (mesmo nucleo) do artigo.
 *
 * Protocolo Prime+Probe na L1 (conjunto-slot 0):
 *   - receptor (contexto 0, main): prime = toca todas as d linhas do anel
 *     (base + i*L1S), i=0..d-1; depois de o transmissor agir, cronometra
 *     o anel; vítima (base) L1-hit (bit 0) ou L1-miss (bit 1).
 *   - transmissor (contexto 1, pthread via clone): bit 1 -> toca o
 *     eviction set (d linhas a L1S a partir de base+(d+1)*L1S, mesmo
 *     conjunto da L1) => com d linhas extras a L1 8-way estoura e a
 *     vítima (LRU) e evictada; bit 0 -> nada.
 *
 * Resultados medidos (gem5 25.1 pinado): sob LRU a vitima e evictada pelo
 * flood e o canal decodifica com erro zero (0/64; lat bit1=374, bit0=182);
 * sob SRRIP/RRIP o scan do RRIP incrementa TODAS as linhas do conjunto a
 * cada eviccao (inclusive quentes, RRPV=0) e o mesmo flood evicta a vitima:
 * o canal continua operacional (0/64) - nao ha colapso neste cenario de
 * flood cross-thread. Somente BRRIP degrada o canal (5/64; 218 vs 198).
 *
 * Rendezvous por flags volateis (processo unico, memoria compartilhada).
 *
 * Uso: channel_2t --out <csv> [--msg hex] [-d n] [-K n] [--warmup n]
 */

#include <inttypes.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define L1S 4096ul /* stride de um conjunto de L1 (32KiB/8/64) */
#define PRIME_P 6  /* passes do prime (cede retencao RRPV=0 as linhas vivas) */

volatile int g_phase = 0; /* 0=init, 1=janela tx, 2=decode */
static volatile uint8_t *g_base;

static uint64_t rdtsc(void)
{
    uint32_t lo, hi;
    __asm__ __volatile__("rdtsc" : "=a"(lo), "=d"(hi));
    return ((uint64_t)hi << 32) | lo;
}

static inline void touch(const volatile void *p)
{
    (void)*(volatile const uint8_t *)(uintptr_t)p;
}

static int bit_at(uint64_t lo, uint64_t hi, int b)
{
    if (b < 32)
        return (int)((hi >> (31 - b)) & 1);
    return (int)((lo >> (63 - b)) & 1);
}

struct snd_args { uint64_t hi, lo; int nbits, warmup, d, tail; };

static void *sender_thread(void *arg)
{
    struct snd_args *a = (struct snd_args *)arg;
    const volatile uint8_t *evict = g_base + (size_t)(a->d + 1) * L1S;
    int rounds = a->warmup + a->nbits + a->tail;
    for (int r = 0; r < rounds; r++) {
        int b = (r >= a->warmup && r < a->warmup + a->nbits)
                    ? bit_at(a->lo, a->hi, r - a->warmup) : 0;
        while (g_phase != 1)
            ;
        if (b == 1)
            for (int k = 0; k < a->d; k++)
                touch(evict + (size_t)k * L1S);
        g_phase = 2;
    }
    return NULL;
}

static void receiver_main(uint64_t hi, uint64_t lo, int nbits, int warmup,
                          int d, int K, int tail, const char *out)
{
    const volatile uint8_t *base = g_base;
    FILE *fp = fopen(out, "w");
    if (!fp) {
        perror("fopen");
        exit(1);
    }
    fprintf(fp, "#d=%d K=%d warmup=%d tail=%d PRIME_P=%d\n", d, K, warmup,
            tail, PRIME_P);
    fprintf(fp, "round,bit,lat_cycles\n");

    char *rows = malloc((size_t)nbits * 32);
    if (!rows) {
        perror("malloc");
        exit(1);
    }
    char *cur = rows;

    int rounds = warmup + nbits + tail;
    for (int r = 0; r < rounds; r++) {
        int measured = r >= warmup && r < warmup + nbits;
        int b = measured ? bit_at(lo, hi, r - warmup) : 0;

        /* prime: d linhas do anel entram na L1 (P passes => RRPV=0) */
        for (int p = 0; p < PRIME_P; p++)
            for (int i = 0; i < d; i++)
                touch(base + (size_t)i * L1S);

        g_phase = 1; /* abre a janela do transmissor (Ts) */
        while (g_phase != 2)
            ;

        /* medida: ponteiro-chasing ciclico sobre as d linhas do anel */
        uint64_t p = (uint64_t)(uintptr_t)base;
        uint64_t t0 = rdtsc();
        for (int k = 0; k < K; k++)
            p = *(volatile uint64_t *)(uintptr_t)p;
        uint64_t t1 = rdtsc();

        if (measured) {
            int n = sprintf(cur, "%d,%d,%" PRIu64 "\n", r - warmup, b, t1 - t0);
            cur += n;
        }

        g_phase = 0;
    }
    fwrite(rows, 1, (size_t)(cur - rows), fp);
    free(rows);
    fclose(fp);
}

int main(int argc, char **argv)
{
    uint64_t hi = 0xdeadbeefUL, lo = 0xcafebabeUL;
    int d = 8, warmup = 32, K = 0, tail = 8;
    const char *out = "channel_2t.csv";

    for (int i = 1; i < argc; i++) {
        const char *x = argv[i];
        if (!strcmp(x, "--out") && i + 1 < argc) {
            out = argv[++i];
        } else if (!strcmp(x, "--msg") && i + 1 < argc) {
            const char *s = argv[++i];
            size_t len = strlen(s);
            if (len <= 8) {
                hi = 0;
                lo = (uint64_t)strtoull(s, NULL, 16);
            } else if (len <= 16) {
                char a[9] = {0}, b[9] = {0};
                size_t hlen = len - 8;
                memcpy(a, s, hlen);
                memcpy(b, s + hlen, 8);
                hi = (uint64_t)strtoull(a, NULL, 16);
                lo = (uint64_t)strtoull(b, NULL, 16);
            }
        } else if (!strcmp(x, "-d") && i + 1 < argc) {
            d = atoi(argv[++i]);
        } else if (!strcmp(x, "-K") && i + 1 < argc) {
            K = atoi(argv[++i]);
        } else if (!strcmp(x, "--warmup") && i + 1 < argc) {
            warmup = atoi(argv[++i]);
        }
    }
    if (K <= 0)
        K = d;

    /* base .. base+(d-1)*L1S: anel do receptor (mesma L1 set).
     * base+(d+1)*L1S .. +d*L1S: eviction set do transmissor (mesma set). */
    uint8_t *buf = aligned_alloc(L1S, (size_t)(2 * d + 2) * L1S);
    memset(buf, 0, (size_t)(2 * d + 2) * L1S);
    g_base = buf;
    for (int i = 0; i < d; i++)
        *(uint64_t *)(uintptr_t)(buf + (size_t)i * L1S)
            = (uint64_t)(uintptr_t)(buf + (size_t)((i + 1) % d) * L1S);

    struct snd_args sa = { hi, lo, 64, warmup, d, tail };

    pthread_t st;
    if (pthread_create(&st, NULL, sender_thread, &sa) != 0) {
        perror("pthread_create");
        exit(1);
    }
    receiver_main(hi, lo, 64, warmup, d, K, tail, out);
    pthread_join(st, NULL);

    printf("channel_2t: d=%d K=%d warmup=%d bits=64 msg=%016" PRIx64 "%016" PRIx64 "\n",
           d, K, warmup, hi, lo);
    return 0;
}