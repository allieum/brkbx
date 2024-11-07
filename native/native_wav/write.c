// Include the header file to get access to the MicroPython API
#include "py/dynruntime.h"
#include "py/mpprint.h"

// Helper function to compute factorial
/* static mp_int_t write_helper(mp_int_t x) { */
/*     int i; */
/*     for (i = 0; i < x; i++) {} */
/*     return i; */
/*     /\* if (x == 0) { *\/ */
/*     /\*     return 1.0; *\/ */
/*     /\* } *\/ */
/*     /\* return x * factorial_helper(x - 1); *\/ */
/* } */

// This is the function which will be called from Python, as factorial(x)
/* static mp_obj_t write(mp_obj_t audio_out, */
/*                       mp_obj_t source_samples, */
/*                       mp_obj_t stretch_block_input_samples_int, */
/*                       mp_obj_t stretch_block_output_samples_int, */
/*                       mp_obj_t target_samples_int, */
/*                       mp_obj_t pitched_samples_int) { */
/*                       mp_obj_t pitch_rate_float) { */
static mp_obj_t write(size_t n_args, const mp_obj_t* args) {
    /* mp_printf(&mp_plat_print, "entering native_wav:write with %d args\n", n_args); */
    // Extract the integer from the MicroPython input object
    /* mp_int_t x = mp_obj_get_int(x_obj); */
    mp_obj_t audio_out = args[0];
    mp_buffer_info_t outbufinfo;
    /* mp_printf(&mp_plat_print, "getting audio_out buffer\n"); */
    mp_get_buffer_raise(audio_out, &outbufinfo, MP_BUFFER_WRITE);
    uint16_t *out_buf = (uint16_t*) outbufinfo.buf;
    /* mp_printf(&mp_plat_print, "got audio_out buffer length %d\n", outbufinfo.len); */
    mp_obj_t source_samples = args[1];
    mp_buffer_info_t sourcebufinfo;
    mp_get_buffer_raise(source_samples, &sourcebufinfo, MP_BUFFER_READ);
    const uint16_t *source_buf = (const uint16_t*) sourcebufinfo.buf;

    mp_int_t stretch_block_input_samples = mp_obj_get_int(args[2]);
    mp_int_t stretch_block_output_samples = mp_obj_get_int(args[3]);
    mp_int_t target_samples = mp_obj_get_int(args[4]);
    mp_int_t pitched_samples = mp_obj_get_int(args[5]);
    mp_float_t pitch_rate = mp_obj_get_float(args[6]);
    // Calculate the factorial
    /* mp_int_t result = write_helper(x); */
    // Convert the result to a MicroPython integer object and return it

    int samples_written = 0;
    for (int sample_offset = 0; sample_offset < pitched_samples; sample_offset += stretch_block_input_samples) {
        for (int i = 0; i < stretch_block_output_samples; ++i) {
            int block_i = i % MIN(stretch_block_input_samples, pitched_samples - sample_offset);
            int j = pitch_rate * (sample_offset + block_i);
            out_buf[samples_written++] = source_buf[j];
            if (samples_written == target_samples) {
                return mp_obj_new_int(samples_written);
            }
        }
    }

    return mp_obj_new_int(samples_written);
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
