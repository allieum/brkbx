// Include the header file to get access to the MicroPython API
#include "py/dynruntime.h"

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
static mp_obj_t write(mp_obj_t x_obj) {
    // Extract the integer from the MicroPython input object
    /* mp_int_t x = mp_obj_get_int(x_obj); */
    mp_buffer_info_t bufinfo;
    mp_get_buffer_raise(x_obj, &bufinfo, MP_BUFFER_WRITE);
    byte *buf = (byte*) bufinfo.buf;
    for (int i = 0; i < bufinfo.len; i++) {
        buf[i] = i;
    }
    // Calculate the factorial
    /* mp_int_t result = write_helper(x); */
    // Convert the result to a MicroPython integer object and return it
    return mp_obj_new_int(bufinfo.len);
}
// Define a Python reference to the function above
static MP_DEFINE_CONST_FUN_OBJ_1(write_obj, write);

// This is the entry point and is called when the module is imported
mp_obj_t mpy_init(mp_obj_fun_bc_t *self, size_t n_args, size_t n_kw, mp_obj_t *args) {
    // This must be first, it sets up the globals dict and other things
    MP_DYNRUNTIME_INIT_ENTRY

    // Make the function available in the module's namespace
    mp_store_global(MP_QSTR_write, MP_OBJ_FROM_PTR(&write_obj));

    // This must be last, it restores the globals dict
    MP_DYNRUNTIME_INIT_EXIT
}
