/* Headless libretro runner for testing: scripted input, screenshots (PPM), WAV audio,
 * and RAM probes.  usage: runner core.so rom.md script.txt outprefix [ramaddr ...]
 * script lines:  <from> <to> <buttons>   (buttons: U D L R A B C S, '-' for none)
 *                shot <frame>             (write outprefix_<frame>.ppm)
 *                end <frame>                                                     */
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include "libretro.h"

static uint16_t fb[1024 * 512];
static unsigned fw, fh;
static FILE *wav;
static long wav_samples;
static uint16_t cur_mask;

static bool env_cb(unsigned cmd, void *data) {
    switch (cmd) {
    case RETRO_ENVIRONMENT_GET_SYSTEM_DIRECTORY:
    case RETRO_ENVIRONMENT_GET_SAVE_DIRECTORY: *(const char **)data = "/tmp"; return true;
    case RETRO_ENVIRONMENT_SET_PIXEL_FORMAT: return *(enum retro_pixel_format *)data == RETRO_PIXEL_FORMAT_RGB565;
    case RETRO_ENVIRONMENT_GET_VARIABLE: return false;
    case RETRO_ENVIRONMENT_GET_CAN_DUPE: *(bool *)data = true; return true;
    default: return false;
    }
}
static void video_cb(const void *data, unsigned w, unsigned h, size_t pitch) {
    if (!data) return;
    fw = w; fh = h;
    for (unsigned y = 0; y < h; y++) memcpy(fb + y * w, (const uint8_t *)data + y * pitch, w * 2);
}
static void audio_cb(int16_t l, int16_t r) { int16_t s[2] = { l, r }; fwrite(s, 4, 1, wav); wav_samples++; }
static size_t audio_batch_cb(const int16_t *d, size_t frames) { fwrite(d, 4, frames, wav); wav_samples += frames; return frames; }
static void input_poll_cb(void) {}
static int16_t input_state_cb(unsigned port, unsigned dev, unsigned idx, unsigned id) {
    if (port != 0 || dev != RETRO_DEVICE_JOYPAD) return 0;
    if (id == RETRO_DEVICE_ID_JOYPAD_MASK) return cur_mask;
    return (cur_mask >> id) & 1;
}
static uint16_t parse_buttons(const char *s) {
    uint16_t m = 0;
    for (; *s; s++) switch (*s) {
        case 'U': m |= 1 << RETRO_DEVICE_ID_JOYPAD_UP; break;
        case 'D': m |= 1 << RETRO_DEVICE_ID_JOYPAD_DOWN; break;
        case 'L': m |= 1 << RETRO_DEVICE_ID_JOYPAD_LEFT; break;
        case 'R': m |= 1 << RETRO_DEVICE_ID_JOYPAD_RIGHT; break;
        case 'A': m |= 1 << RETRO_DEVICE_ID_JOYPAD_Y; break;
        case 'B': m |= 1 << RETRO_DEVICE_ID_JOYPAD_B; break;
        case 'C': m |= 1 << RETRO_DEVICE_ID_JOYPAD_A; break;
        case 'S': m |= 1 << RETRO_DEVICE_ID_JOYPAD_START; break;
    }
    return m;
}
static void wav_header(FILE *f, long n) {
    uint32_t sr = 44100, br = sr * 4, ds = n * 4, cs = 36 + ds;
    fseek(f, 0, SEEK_SET);
    fwrite("RIFF", 1, 4, f); fwrite(&cs, 4, 1, f); fwrite("WAVEfmt ", 1, 8, f);
    uint32_t v32 = 16; fwrite(&v32, 4, 1, f);
    uint16_t v16 = 1; fwrite(&v16, 2, 1, f); v16 = 2; fwrite(&v16, 2, 1, f);
    fwrite(&sr, 4, 1, f); fwrite(&br, 4, 1, f); v16 = 4; fwrite(&v16, 2, 1, f); v16 = 16; fwrite(&v16, 2, 1, f);
    fwrite("data", 1, 4, f); fwrite(&ds, 4, 1, f);
}

struct ev { int a, b; uint16_t m; int kind; unsigned addr; };
int main(int argc, char **argv) {
    if (argc < 5) { fprintf(stderr, "usage\n"); return 1; }
    void *h = dlopen(argv[1], RTLD_NOW);
    if (!h) { fprintf(stderr, "%s\n", dlerror()); return 1; }
#define SYM(n) typeof(&n) p_##n = (typeof(&n))dlsym(h, #n)
    SYM(retro_set_environment); SYM(retro_set_video_refresh); SYM(retro_set_audio_sample);
    SYM(retro_set_audio_sample_batch); SYM(retro_set_input_poll); SYM(retro_set_input_state);
    SYM(retro_init); SYM(retro_load_game); SYM(retro_run); SYM(retro_get_memory_data);
    SYM(retro_get_system_av_info);
    p_retro_set_environment(env_cb);
    p_retro_init();
    p_retro_set_video_refresh(video_cb); p_retro_set_audio_sample(audio_cb);
    p_retro_set_audio_sample_batch(audio_batch_cb); p_retro_set_input_poll(input_poll_cb);
    p_retro_set_input_state(input_state_cb);
    FILE *rf = fopen(argv[2], "rb"); fseek(rf, 0, SEEK_END); long sz = ftell(rf); fseek(rf, 0, SEEK_SET);
    void *rom = malloc(sz); fread(rom, 1, sz, rf); fclose(rf);
    struct retro_game_info gi = { argv[2], rom, (size_t)sz, NULL };
    if (!p_retro_load_game(&gi)) { fprintf(stderr, "load failed\n"); return 1; }
    char path[512];
    snprintf(path, sizeof path, "%s.wav", argv[4]);
    wav = fopen(path, "wb"); wav_header(wav, 0);

    struct ev evs[512]; int nev = 0, endf = 600;
    FILE *sf = fopen(argv[3], "r"); char line[256];
    while (fgets(line, sizeof line, sf)) {
        char b[64]; int a, c;
        if (sscanf(line, "shot %d", &a) == 1) { evs[nev].a = a; evs[nev].kind = 1; nev++; }
        else if (sscanf(line, "end %d", &a) == 1) endf = a;
        else if (sscanf(line, "auto %d %d %x", &a, &c, &evs[nev].addr) == 3) { evs[nev].a = a; evs[nev].b = c; evs[nev].kind = 2; nev++; }
        else if (sscanf(line, "%d %d %63s", &a, &c, b) == 3) { evs[nev].a = a; evs[nev].b = c; evs[nev].m = parse_buttons(b); evs[nev].kind = 0; nev++; }
    }
    fclose(sf);
    uint8_t *ram = p_retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM);
    for (int f = 0; f <= endf; f++) {
        cur_mask = 0;
        for (int i = 0; i < nev; i++) if (evs[i].kind == 0 && f >= evs[i].a && f <= evs[i].b) cur_mask |= evs[i].m;
        for (int i = 0; i < nev; i++) if (evs[i].kind == 2 && f >= evs[i].a && f <= evs[i].b) {
            int16_t x = *(int16_t *)(ram + (evs[i].addr & 0xFFFF));
            cur_mask |= 1 << RETRO_DEVICE_ID_JOYPAD_A;           /* gas (Genesis C) */
            if (x > 160) cur_mask |= 1 << RETRO_DEVICE_ID_JOYPAD_LEFT;
            else if (x < -160) cur_mask |= 1 << RETRO_DEVICE_ID_JOYPAD_RIGHT;
        }
        p_retro_run();
        for (int i = 0; i < nev; i++) if (evs[i].kind == 1 && evs[i].a == f) {
            snprintf(path, sizeof path, "%s_%05d.ppm", argv[4], f);
            FILE *o = fopen(path, "wb");
            fprintf(o, "P6\n%u %u\n255\n", fw, fh);
            for (unsigned k = 0; k < fw * fh; k++) {
                uint16_t p = fb[k];
                uint8_t rgb[3] = { (uint8_t)((p >> 11) << 3), (uint8_t)(((p >> 5) & 63) << 2), (uint8_t)((p & 31) << 3) };
                fwrite(rgb, 3, 1, o);
            }
            fclose(o);
            printf("frame %d:", f);
            for (int a = 5; a < argc; a++) {
                unsigned addr = strtoul(argv[a], 0, 16) & 0xFFFF;
                printf(" [%04X]=%u", addr, *(uint16_t *)(ram + addr));
            }
            printf("\n");
        }
    }
    wav_header(wav, wav_samples); fclose(wav);
    return 0;
}
