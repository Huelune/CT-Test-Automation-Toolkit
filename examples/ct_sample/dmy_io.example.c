/* Fabricated sample for todo.md section 2. Not customer code.
 * Keep this file ASCII only so any CT toolchain reads it the same way.
 * Every name starts with dmy_ so the exported files can be searched for it.
 */

typedef struct {
    int dmy_lo;
    int dmy_hi;
} dmy_limit_t;

int dmy_gain;            /* read */
unsigned char dmy_mode;  /* read */
dmy_limit_t dmy_limit;   /* read, struct */
int dmy_spare;           /* read, left out of the I/O list */
float dmy_level;         /* written */
int dmy_hist[4];         /* written, array */
int dmy_count;           /* read and written */

int dmy_calc(int dmy_x, const int *dmy_ptr)
{
    int dmy_ret = dmy_x * dmy_gain;

    if (dmy_mode == 1u) {
        dmy_ret += *dmy_ptr;
    }
    if (dmy_spare > 0) {
        dmy_ret -= 1;
    }
    if (dmy_ret < dmy_limit.dmy_lo) {
        dmy_ret = dmy_limit.dmy_lo;
    } else if (dmy_ret > dmy_limit.dmy_hi) {
        dmy_ret = dmy_limit.dmy_hi;
    }
    dmy_level = (float)dmy_ret / 2.0f;
    dmy_hist[dmy_count & 3] = dmy_ret;
    dmy_count++;
    return dmy_ret;
}
