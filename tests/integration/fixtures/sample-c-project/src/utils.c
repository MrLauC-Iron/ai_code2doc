#include <stdio.h>
#include "utils.h"

int add(int a, int b) {
    return a + b;
}

int multiply(int a, int b) {
    return a * b;
}

void print_point(struct Point *p) {
    printf("Point(%d, %d)\n", p->x, p->y);
}
