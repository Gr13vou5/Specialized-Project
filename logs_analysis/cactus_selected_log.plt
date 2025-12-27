#!/usr/bin/gnuplot -persist

set terminal postscript eps enhanced color font "Helvetica,10"

set tics font "Helvetica,18"
set key font "Helvetica,22"

set xlabel "Solved Instances" font "Helvetica,18"
set ylabel "CPU Time [s]" font "Helvetica,18"

set logscale y
set style data linespoints

eps_file = "results/cactus_selected_log.eps"
set output eps_file
csv = "results/time_selected_for_cactus.dat"

cactus(method) = sprintf("< echo 0; grep %s, %s | cut -d',' -f 2 | sort -n", method, csv)

set key top left

plot [0:20] [:1800] \
    cactus("fASP_conj") title "fASP-c" lc rgb "green",\
    cactus("fASP_src")  title "fASP-s" lc rgb "skyblue",\
    cactus("Hybrid_BMSA") title "H.E." lc rgb "dark-green",\
    cactus("PFVS") title "PFVS" lc rgb "black"
