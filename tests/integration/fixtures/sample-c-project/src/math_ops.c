#include "utils.h"

int square(int x) {
    return multiply(x, x);
}

int cube(int x) {
    return multiply(square(x), x);
}
