cmake_minimum_required(VERSION 3.20)
project(sample_c_project C)

add_executable(sample_c_project
    src/main.c
    src/utils.c
    src/math_ops.c
)

target_include_directories(sample_c_project PRIVATE include)
