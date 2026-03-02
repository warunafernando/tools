# Distributed under the OSI-approved BSD 3-Clause License.  See accompanying
# file Copyright.txt or https://cmake.org/licensing for details.

cmake_minimum_required(VERSION 3.5)

file(MAKE_DIRECTORY
  "/home/mini/esp/esp-idf/components/bootloader/subproject"
  "/home/mini/tools/msr1_esp32c6/build/bootloader"
  "/home/mini/tools/msr1_esp32c6/build/bootloader-prefix"
  "/home/mini/tools/msr1_esp32c6/build/bootloader-prefix/tmp"
  "/home/mini/tools/msr1_esp32c6/build/bootloader-prefix/src/bootloader-stamp"
  "/home/mini/tools/msr1_esp32c6/build/bootloader-prefix/src"
  "/home/mini/tools/msr1_esp32c6/build/bootloader-prefix/src/bootloader-stamp"
)

set(configSubDirs )
foreach(subDir IN LISTS configSubDirs)
    file(MAKE_DIRECTORY "/home/mini/tools/msr1_esp32c6/build/bootloader-prefix/src/bootloader-stamp/${subDir}")
endforeach()
if(cfgdir)
  file(MAKE_DIRECTORY "/home/mini/tools/msr1_esp32c6/build/bootloader-prefix/src/bootloader-stamp${cfgdir}") # cfgdir has leading slash
endif()
