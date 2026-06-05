// Include the header file to get access to the MicroPython API
#include "py/dynruntime.h"
#include "py/mpprint.h"
#include <math.h>

// Bhaskara I sin approximation: accurate to 0.17% over [0, π], no trig calls needed.
static float sin_fast(float x) {
    float d = x * (3.14159265f - x);
    return 16.0f * d / (5.0f * 9.8696044f - 4.0f * d);
}

// cos(x) for x in [0, π] via sin identity
static float cos_fast(float x) {
    float half_pi = 1.5707963f;
    if (x <= half_pi)
        return sin_fast(half_pi - x);
    else
        return -sin_fast(x - half_pi);
}

typedef struct {
    float x1, x2, y1, y2;
    float a0, a1, a2, b1, b2;
} BiquadFilter;

// Recalculates coefficients only — does not touch filter state.
static void update_filter_coeffs(BiquadFilter* f, float filter_depth, float samplerate) {
    int is_highpass = filter_depth > 0;
    float depth = fabsf(filter_depth);
    float cutoff;

    if (is_highpass) {
        // Cubic mapping: 20Hz at depth=0, 12000Hz at depth=1
        cutoff = 20.0f + depth * depth * depth * 11980.0f;
    } else {
        // Inverted cubic mapping: 20000Hz at depth=0, 60Hz at depth=1
        float inv = 1.0f - depth;
        cutoff = 60.0f + inv * inv * inv * 19940.0f;
    }

    float nyq = samplerate * 0.47f;
    if (cutoff < 20.0f) cutoff = 20.0f;
    if (cutoff > nyq) cutoff = nyq;

    // Q scales from Butterworth (0.707) up to resonant (3.5) with depth.
    // This gives the classic synth-filter sweep character at high depths.
    float q = 0.707f + depth * depth * 2.8f;

    float w0 = 2.0f * 3.14159265f * cutoff / samplerate;
    float sin_w0 = sin_fast(w0);
    float cos_w0 = cos_fast(w0);
    float alpha = sin_w0 / (2.0f * q);
    float norm = 1.0f / (1.0f + alpha);

    if (is_highpass) {
        f->a0 = (1.0f + cos_w0) * 0.5f * norm;
        f->a1 = -(1.0f + cos_w0) * norm;
        f->a2 = f->a0;
    } else {
        f->a0 = (1.0f - cos_w0) * 0.5f * norm;
        f->a1 = (1.0f - cos_w0) * norm;
        f->a2 = f->a0;
    }
    f->b1 = -2.0f * cos_w0 * norm;
    f->b2 = (1.0f - alpha) * norm;
}

static float process_sample(BiquadFilter* f, float in) {
    float out = f->a0 * in + f->a1 * f->x1 + f->a2 * f->x2
              - f->b1 * f->y1 - f->b2 * f->y2;
    f->x2 = f->x1; f->x1 = in;
    f->y2 = f->y1; f->y1 = out;
    return out;
}

// Persistent filter state, allocated by Python and passed as a buffer.
// Layout: [BiquadFilter 36B][last_depth 4B][initialized 4B] = 44 bytes total.
// initialized==0 on first call (Python bytearray starts zeroed).
typedef struct {
    BiquadFilter filter;
    float last_depth;
    int initialized;
} FilterState;

static mp_obj_t write(size_t n_args, const mp_obj_t* args) {
    mp_obj_t audio_out = args[0];
    mp_buffer_info_t outbufinfo;
    mp_get_buffer_raise(audio_out, &outbufinfo, MP_BUFFER_WRITE);
    int16_t *out_buf = (int16_t*) outbufinfo.buf;

    mp_obj_t source_samples = args[1];
    mp_buffer_info_t sourcebufinfo;
    mp_get_buffer_raise(source_samples, &sourcebufinfo, MP_BUFFER_READ);
    const int16_t *source_buf = (const int16_t*) sourcebufinfo.buf;

    mp_int_t stretch_block_input_samples = mp_obj_get_int(args[2]);
    mp_int_t stretch_block_output_samples = mp_obj_get_int(args[3]);
    mp_int_t target_samples = mp_obj_get_int(args[4]);
    mp_int_t pitched_samples = mp_obj_get_int(args[5]);
    mp_float_t pitch_rate = mp_obj_get_float(args[6]);
    mp_float_t volume = mp_obj_get_float(args[7]);
    mp_float_t filter_depth = mp_obj_get_float(args[8]);
    mp_float_t mix_depth = mp_obj_get_float(args[9]);

    mp_buffer_info_t fsbuf;
    mp_get_buffer_raise(args[10], &fsbuf, MP_BUFFER_WRITE);
    FilterState* fs = (FilterState*)fsbuf.buf;

    // int interpellation_window = 10;

    int sign_changed = fs->initialized && ((filter_depth > 0) != (fs->last_depth > 0));
    if (!fs->initialized || fabsf(filter_depth - fs->last_depth) > 0.0001f) {
        if (sign_changed)
            fs->filter.x1 = fs->filter.x2 = fs->filter.y1 = fs->filter.y2 = 0.0f;
        update_filter_coeffs(&fs->filter, filter_depth, 44100.0f);
        fs->last_depth = filter_depth;
        fs->initialized = 1;
    }

    int samples_written = 0;
    for (int sample_offset = 0; sample_offset < pitched_samples; sample_offset += stretch_block_input_samples) {
        for (int i = 0; i < stretch_block_output_samples; ++i) {
            int stretch_block_size = MIN(stretch_block_input_samples, pitched_samples - sample_offset);
            int block_i = i % stretch_block_size;

            float sample;
            // int block_samples_left = stretch_block_output_samples - i;
            // if (block_samples_left < interpellation_window && sample_offset + stretch_block_input_samples < pitched_samples) {
            //     int16_t prev_sample = out_buf[samples_written - 1];
            //     int next_block_j = pitch_rate * (sample_offset + stretch_block_input_samples);
            //     int16_t next_block_start_sample = source_buf[next_block_j];
            //     sample = prev_sample + (next_block_start_sample - prev_sample) / block_samples_left;
            // } else {
            int j = pitch_rate * (sample_offset + block_i);
            sample = source_buf[j];
            // }

            // Apply filter and volume
            sample = process_sample(&fs->filter, sample) * volume + mix_depth * out_buf[samples_written];
            out_buf[samples_written++] = (int16_t)sample;
            /* mp_printf(&mp_plat_print, "native_wav: block_i = %d, j = %d\n", block_i, j); */
            if (samples_written == target_samples) {
                return mp_obj_new_int(2 * samples_written);
            }
        }
    }

    return mp_obj_new_int(2 * samples_written);
}
// Define a Python reference to the function above
static MP_DEFINE_CONST_FUN_OBJ_VAR(write_obj, 0, write);

// This is the entry point and is called when the module is imported
mp_obj_t mpy_init(mp_obj_fun_bc_t *self, size_t n_args, size_t n_kw, mp_obj_t *args) {
    // This must be first, it sets up the globals dict and other things
    MP_DYNRUNTIME_INIT_ENTRY

    mp_printf(&mp_plat_print, "initialising module self=%p\n", self);

    // Make the function available in the module's namespace
    mp_store_global(MP_QSTR_write, MP_OBJ_FROM_PTR(&write_obj));

    // This must be last, it restores the globals dict
    MP_DYNRUNTIME_INIT_EXIT
}
