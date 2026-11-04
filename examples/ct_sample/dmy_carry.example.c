/* Fabricated sample for todo.md section 24. Not customer code.
 * Keep this file ASCII only so any CT toolchain reads it the same way.
 * Every name starts with dmy_ so the exported files can be searched for it.
 *
 * Each global reaches the output of dmy_carry in a different way, to see which
 * ones CT leaves unchecked in the global variable [Edit] list of a new test.
 */

int dmy_pick(int dmy_i);    /* dmy_rec.c: writes dmy_sum and dmy_recs */

int dmy_c_direct;           /* written by dmy_carry itself */
int dmy_c_callee;           /* written by dmy_c_helper, which dmy_carry calls */
int dmy_c_ptr;              /* written through the global pointer dmy_c_p */
int *dmy_c_p = &dmy_c_ptr;
unsigned short dmy_c_unused; /* not touched by dmy_carry */

static void dmy_c_helper(int dmy_v)
{
    dmy_c_callee = dmy_v;
}

int dmy_carry(int dmy_v)
{
    dmy_c_direct = dmy_v;
    dmy_c_helper(dmy_v + 1);
    *dmy_c_p = dmy_v + 2;
    return dmy_pick(dmy_v);
}
