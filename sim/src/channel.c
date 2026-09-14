/*
 * driver do canal encoberto baseado em estado de cache (Algoritmo 1,
 * Xiong & Szefer) - PoC de fio unico para validacao em modo SE do gem5.
 *
 * O programa assume os dois papeis em sequencia dentro de um unico fio:
 *   - ~receptor~: fase de iniciacao (init) e decodificacao (decode+medida);
 *   - ~transmissor~: toca a linha compartilhada (line[0]) se o bit e 1.
 *
 * O estado da politica de substituicao (LRU hoje, SRRIP na fase 4) e o
 * canal: a linha line[0] esta presente na cache apos o decode sse o bit
 * transmitido foi 1. Cronometramos com pointer-chasing de 7 elementos.
 *
 * Todos os *touches* sao LEITURAS: o conteudo das linhas nao muda (a
 * linha 0 carrega o ponteiro inicial da cadeia medida).
 *
 * Uso: channel [opcoes]
 *   --msg <hex>    mensagem a transmitir (default deadbeefcafebabe)
 *   -d <n>         numero de linhas da fase de decode/evicao (default 8)
 *   --stride <b>   distancia entre linhas do mesmo conjunto (default 4096)
 *   --set <s>      indice do conjunto alvo (default 0)
 *   --chase <k>    profundidade do pointer-chasing (default 7)
 *   --warmup <n>   rodadas de aquecimento (default 32)
 *   --alg <1|2>    Algoritmo 1 (toca a linha compartilhada 0) ou
 *                  Algoritmo 2 (toca uma linha propria, no mesmo conjunto)
 *   --out <path>   arquivo CSV de saida (por rodada)
 */

#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint64_t rdtsc(void)
{
    uint32_t lo, hi;
    __asm__ __volatile__("rdtsc" : "=a"(lo), "=d"(hi));
    return ((uint64_t)hi << 32) | lo;
}

/* leitura volatil: accesso de cache sem alterar o conteudo da linha */
static inline void touch(const void *p)
{
    (void)*(volatile const uint8_t *)(uintptr_t)p;
}

/* converte o bit b da mensagem (big-endian: bit 0 = MSB de msg_hi) */
static int bit_at(uint64_t msg_lo, uint64_t msg_hi, int b)
{
    if (b < 32)
        return (int)((msg_hi >> (31 - b)) & 1);
    return (int)((msg_lo >> (63 - b)) & 1);
}

int main(int argc, char **argv)
{
    uint64_t msg_hi = 0xdeadbeefUL;
    uint64_t msg_lo = 0xcafebabeUL;
    int d = 8;
    size_t stride = 4096;
    size_t set_idx = 0;
    int chase = 7;
    int warmup = 32;
    int alg = 1;
    const char *out = NULL;

    for (int i = 1; i < argc; i++) {
        const char *a = argv[i];
        if (!strcmp(a, "--msg") && i + 1 < argc) {
            const char *s = argv[++i];
            size_t len = strlen(s);
            if (len <= 8) {
                msg_hi = 0;
                msg_lo = (uint64_t)strtoull(s, NULL, 16);
            } else if (len <= 16) {
                char hi_s[9] = {0}, lo_s[9] = {0};
                size_t hlen = len - 8;
                memcpy(hi_s, s, hlen);
                memcpy(lo_s, s + hlen, 8);
                msg_hi = (uint64_t)strtoull(hi_s, NULL, 16);
                msg_lo = (uint64_t)strtoull(lo_s, NULL, 16);
            } else {
                fprintf(stderr, "msg deve ter <= 16 hex digits\n");
                return 1;
            }
        } else if (!strcmp(a, "-d") && i + 1 < argc) {
            d = atoi(argv[++i]);
        } else if (!strcmp(a, "--stride") && i + 1 < argc) {
            stride = (size_t)strtoull(argv[++i], NULL, 0);
        } else if (!strcmp(a, "--set") && i + 1 < argc) {
            set_idx = (size_t)strtoull(argv[++i], NULL, 0);
        } else if (!strcmp(a, "--chase") && i + 1 < argc) {
            chase = atoi(argv[++i]);
        } else if (!strcmp(a, "--warmup") && i + 1 < argc) {
            warmup = atoi(argv[++i]);
        } else if (!strcmp(a, "--alg") && i + 1 < argc) {
            alg = atoi(argv[++i]);
        } else if (!strcmp(a, "--out") && i + 1 < argc) {
            out = argv[++i];
        }
    }

    int nbits = 64;
    if (d < 2) {
        fprintf(stderr, "d deve ser >= 2\n");
        return 1;
    }
    if (alg != 1 && alg != 2) {
        fprintf(stderr, "--alg deve ser 1 ou 2\n");
        return 1;
    }

    /* linhas do conjunto alvo: base + i*stride, todas no mesmo conjunto.
     * (assumindo stride multiplo de 64 linhas de cache). */
    uint8_t *base = aligned_alloc(stride, (size_t)(d + 4) * stride + 64);
    memset(base, 0, (size_t)(d + 4) * stride + 64);
    uint8_t *line = base + set_idx * 64;

    /* buffer do pointer-chasing (fora do conjunto alvo) */
    uint8_t *cbuf = aligned_alloc(64, 64);
    memset(cbuf, 0, 64);
    uint64_t *cb = (uint64_t *)cbuf;
    for (int i = 0; i < chase - 1; i++)
        cb[i] = (uint64_t)(uintptr_t)&cb[i + 1];
    if (chase >= 1)
        cb[chase - 1] = 0; /* sentinela */

    uint8_t *l0 = line;
    uint8_t *l_init = line + stride;              /* linhas 1..d-1 */
    uint8_t *l_helper = line + (size_t)d * stride; /* linha de decode */
    uint8_t *l_last = line + (size_t)(d + 1) * stride;
    uint8_t *l_snd = line + (size_t)(d + 2) * stride; /* linha do transmissor (Alg. 2) */

    /* linha 0 carrega o inicio da cadeia medida */
    *(uint64_t *)(uintptr_t)l0 = (uint64_t)(uintptr_t)cb;
    touch(cbuf);

    FILE *fp = NULL;
    if (out) {
        fp = fopen(out, "w");
        if (!fp) {
            perror("fopen");
            return 1;
        }
        fprintf(fp, "round,bit,lat_cycles\n");
    }

    int rounds = warmup + nbits;
    for (int r = 0; r < rounds; r++) {
        int b = (r >= warmup) ? bit_at(msg_lo, msg_hi, r - warmup) : 0;

        /* RECEPTOR: init - enche o conjunto com d-1 linhas (1..d-1) */
        for (int i = 1; i < d; i++)
            touch(l_init + (size_t)(i - 1) * stride);

        /* TRANSMISSOR: codifica o bit.
         * Alg. 1: toca a linha compartilhada (line 0) se bit=1.
         * Alg. 2: toca uma linha propria (l_snd) no mesmo conjunto. */
        if (b == 1)
            touch(alg == 1 ? l0 : l_snd);

        /* RECEPTOR: decode - linhas helper forcando evicao + medida */
        touch(l_helper);
        touch(l_last);

        /* cronometra a presenca da linha 0 via pointer-chasing */
        uint64_t p = (uint64_t)(uintptr_t)l0;
        uint64_t t0 = rdtsc();
        for (int k = 0; k < chase; k++)
            p = *(volatile uint64_t *)(uintptr_t)p;
        uint64_t t1 = rdtsc();

        if (r >= warmup) {
            if (fp)
                fprintf(fp, "%d,%d,%" PRIu64 "\n", r - warmup, b, t1 - t0);
        }
    }

    if (fp)
        fclose(fp);

    printf("channel: d=%d stride=%zu set=%zu chase=%d warmup=%d bits=%d alg=%d out=%s\n",
           d, stride, set_idx, chase, warmup, nbits, alg, out ? out : "-");
    return 0;
}