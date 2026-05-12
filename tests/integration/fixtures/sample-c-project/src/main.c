#include <stdio.h>
#include "utils.h"

int main(void) {
    struct Point p;
    p.x = 10;
    p.y = 20;

    int sum = add(p.x, p.y);
    int product = multiply(p.x, p.y);

    printf("Sum: %d\n", sum);
    printf("Product: %d\n", product);
    print_point(&p);

    return 0;
}
