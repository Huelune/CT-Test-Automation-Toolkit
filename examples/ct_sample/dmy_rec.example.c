/* Fabricated sample for todo.md section 19. Not customer code.
 * Keep this file ASCII only so any CT toolchain reads it the same way.
 * Every name starts with dmy_ so the exported files can be searched for it.
 */

typedef struct {
    int dmy_s;
    int dmy_t;
} dmy_rec_t;

dmy_rec_t dmy_recs[4];   /* read and written, array of struct */
int dmy_sum;             /* written */

int dmy_pick(int dmy_i)
{
    dmy_recs[dmy_i & 3].dmy_t = dmy_recs[dmy_i & 3].dmy_s + 1;
    dmy_sum = dmy_recs[0].dmy_s + dmy_recs[2].dmy_t;
    return dmy_recs[3].dmy_t;
}
