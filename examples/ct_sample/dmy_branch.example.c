/* Fabricated sample for todo.md section 28. Not customer code.
 * Keep this file ASCII only so any CT toolchain reads it the same way.
 * Every name starts with dmy_ so the exported files can be searched for it.
 *
 * dmy_branch has seven decisions (listed in the answer table below). The cases below are chosen so that each
 * decision goes a different way, to see where CT stores the branch results of
 * each test case.
 */

int dmy_branch(int dmy_a, int dmy_b)
{
    int dmy_r;
    int dmy_i;

    if (dmy_a > 10) {
        dmy_r = 1;
    } else if (dmy_a < 0) {
        dmy_r = 2;
    } else {
        dmy_r = 3;
    }

    switch (dmy_b) {
    case 1:
        dmy_r += 10;
        break;
    case 2:
        dmy_r += 20;
        break;
    default:
        dmy_r += 30;
        break;
    }

    for (dmy_i = 0; dmy_i < dmy_b; dmy_i++) {
        dmy_r++;
    }

    if (dmy_a == 5 && dmy_b == 5) {
        dmy_r += 100;
    }

    while (dmy_r > 100) {
        dmy_r -= 100;
    }

    return (dmy_r > 20) ? dmy_r : -dmy_r;
}

/* Answer table (case inputs and expected return values):
 *
 * case        dmy_a  dmy_b  return
 * dmy_case_a     20      1     -12
 * dmy_case_b     -3      2      24
 * dmy_case_c      5      0      33
 * dmy_case_d      5      5      38
 *
 * decision (source order)          a      b      c        d
 * 1 if (dmy_a > 10)                T      F      F        F
 * 2 else if (dmy_a < 0)            -      T      F        F
 * 3 switch (dmy_b)                 case 1 case 2 default  default
 * 4 for (dmy_i < dmy_b)            T/F    T/F    F        T/F
 * 5 if (dmy_a == 5 && dmy_b == 5)  F      F      F        T
 * 6 while (dmy_r > 100)            F      F      F        T/F
 * 7 (dmy_r > 20) ? :               F      T      T        T
 *     (row 7 counts only when the project's ternary-operator setting is on;
 *      see the CT 2025.12 coverage settings)
 *
 * If CT counts each condition of && as its own branch, decision 5 splits into:
 * 5a dmy_a == 5                    F      F      T        T
 * 5b dmy_b == 5                    -      -      F        T
 * (a=20 is F so b is not evaluated; a=-3 is F; c: a=5 T then b=0 F;
 *  d: a=5 T then b=5 T)
 */
