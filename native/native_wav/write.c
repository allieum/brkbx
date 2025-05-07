// Include the header file to get access to the MicroPython API
#include "py/dynruntime.h"
#include "py/mpprint.h"
#include <math.h>

static float sinfest(float x) {
    // Normalize x to 0..2π
    x = x - ((int)(x / (2 * 3.14159f))) * 2 * 3.14159f;

    // Simple polynomial approximation
    float x2 = x * x;
    float x3 = x2 * x;
    float x5 = x3 * x2;
    return x - (x3 / 6.0f) + (x5 / 120.0f);
}

static float cosfest(float x) {
    return sinfest(x + 3.14159f / 2);
}

typedef struct {
    float x1, x2, y1, y2;
    float a0, a1, a2, b1, b2;
} BiquadFilter;

static void init_filter(BiquadFilter* f, float filter_depth, float samplerate) {
    float cutoff;
    int is_highpass = filter_depth > 0;

    // Convert filter_depth to cutoff frequency
    if (is_highpass) {
        cutoff = 500.0f + (filter_depth * 4000.0f);
    } else {
        // More gradual LPF curve, especially for small negative values
        cutoff = 12000.0f - (fabs(filter_depth) * 10000.0f);
    }

    // Ensure cutoff stays in safe range
    cutoff = cutoff < 200.0f ? 200.0f : cutoff;
    cutoff = cutoff > samplerate/2.5f ? samplerate/2.5f : cutoff;

    float w0 = 2.0f * 3.14159f * cutoff / samplerate;
    float alpha = sinfest(w0) * 0.707f;
    float cosw0 = cosfest(w0);
    float norm = 1.0f / (1.0f + alpha);

    if (is_highpass) {
        // High-pass coefficients
        f->a0 = (1.0f + cosw0) * 0.5f * norm;
        f->a1 = -(1.0f + cosw0) * norm;
        f->a2 = f->a0;
    } else {
        // Low-pass coefficients
        f->a0 = (1.0f - cosw0) * 0.5f * norm;
        f->a1 = (1.0f - cosw0) * norm;
        f->a2 = f->a0;
    }

    f->b1 = -2.0f * cosw0 * norm;
    f->b2 = (1.0f - alpha) * norm;
    f->x1 = f->x2 = f->y1 = f->y2 = 0.0f;
}

static float process_sample(BiquadFilter* f, float in) {
    float out = f->a0 * in + f->a1 * f->x1 + f->a2 * f->x2 -
                f->b1 * f->y1 - f->b2 * f->y2;

    f->x2 = f->x1;
    f->x1 = in;
    f->y2 = f->y1;
    f->y1 = out;

    return out;
}
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
    mp_float_t filter_depth = mp_obj_get_float(args[8]); // New parameter

    int interpellation_window = 10;

    BiquadFilter filter;
    init_filter(&filter, filter_depth, 44100.0f);

    int samples_written = 0;
    for (int sample_offset = 0; sample_offset < pitched_samples; sample_offset += stretch_block_input_samples) {
        for (int i = 0; i < stretch_block_output_samples; ++i) {
            int stretch_block_size = MIN(stretch_block_input_samples, pitched_samples - sample_offset);
            int block_i = i % stretch_block_size;

            float sample;
            int block_samples_left = stretch_block_output_samples - i;
            if (block_samples_left < interpellation_window && sample_offset + stretch_block_input_samples < pitched_samples) {
                int16_t prev_sample = out_buf[samples_written - 1];
                int next_block_j = pitch_rate * (sample_offset + stretch_block_input_samples);
                int16_t next_block_start_sample = source_buf[next_block_j];
                sample = prev_sample + (next_block_start_sample - prev_sample) / block_samples_left;
            } else {
                int j = pitch_rate * (sample_offset + block_i);
                sample = source_buf[j];
            }

            // Apply filter and volume
            sample = process_sample(&filter, sample) * volume;
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
