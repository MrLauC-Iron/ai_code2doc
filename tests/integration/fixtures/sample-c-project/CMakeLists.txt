cmake_minimum_required(VERSION 3.20)
project(sample_c_project C)

find_package(Math)

add_library(utils STATIC src/utils.c)
target_include_directories(utils PUBLIC include)

add_library(math_ops STATIC src/math_ops.c)
target_link_libraries(math_ops PUBLIC utils)

add_executable(sample_c_project src/main.c)
target_link_libraries(sample_c_project PRIVATE utils math_ops)
