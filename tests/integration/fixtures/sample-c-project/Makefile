CC = gcc
CFLAGS = -Wall -Wextra -Iinclude

SRCS = src/main.c src/utils.c src/math_ops.c
OBJS = $(SRCS:.c=.o)
TARGET = sample_c_project

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) -o $@ $^

%.o: %.c
	$(CC) $(CFLAGS) -c -o $@ $<

clean:
	rm -f $(OBJS) $(TARGET)

.PHONY: all clean
