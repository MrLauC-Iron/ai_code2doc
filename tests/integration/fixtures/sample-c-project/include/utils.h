#ifndef UTILS_H
#define UTILS_H

typedef int BOOL;
#define TRUE 1
#define FALSE 0

struct Point {
    int x;
    int y;
};

enum Color {
    RED,
    GREEN,
    BLUE
};

int add(int a, int b);
int multiply(int a, int b);
void print_point(struct Point *p);

#endif /* UTILS_H */
