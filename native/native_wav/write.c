// Include the header file to get access to the MicroPython API
#include "py/dynruntime.h"
#include "py/mpprint.h"

static mp_obj_t write(size_t n_args, const mp_obj_t* args) {
    mp_obj_t audio_out = args[0];
    mp_buffer_info_t outbufinfo;
    mp_get_buffer_raise(audio_out, &outbufinfo, MP_BUFFER_WRITE);
    uint16_t *out_buf = (uint16_t*) outbufinfo.buf;

    mp_obj_t source_samples = args[1];
    mp_buffer_info_t sourcebufinfo;
    mp_get_buffer_raise(source_samples, &sourcebufinfo, MP_BUFFER_READ);
    const uint16_t *source_buf = (const uint16_t*) sourcebufinfo.buf;

    mp_int_t stretch_block_input_samples = mp_obj_get_int(args[2]);
    mp_int_t stretch_block_output_samples = mp_obj_get_int(args[3]);
    mp_int_t target_samples = mp_obj_get_int(args[4]);
    mp_int_t pitched_samples = mp_obj_get_int(args[5]);
    mp_float_t pitch_rate = mp_obj_get_float(args[6]);

    int samples_written = 0;
    for (int sample_offset = 0; sample_offset < pitched_samples; sample_offset += stretch_block_input_samples) {
        for (int i = 0; i < stretch_block_output_samples; ++i) {
            int block_i = i % MIN(stretch_block_input_samples, pitched_samples - sample_offset);
            int j = pitch_rate * (sample_offset + block_i);
            out_buf[samples_written++] = source_buf[j];
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
