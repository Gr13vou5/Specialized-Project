#!/usr/bin/gnuplot -persist

set terminal postscript eps enhanced color font "Helvetica,10"

set tics font "Helvetica,18"
set key font "Helvetica,20"

set xlabel "Solved Instances" font "Helvetica,18"
set ylabel "CPU Time [s]" font "Helvetica,18"

eps_file = "results/cactus_all_log.eps"
set output eps_file
csv = "results/time_all_for_cactus.dat"

cactus(method) = sprintf("< echo 0; grep %s, %s | cut -d',' -f 2 | sort -n", method, csv)

set key top left
set style data linespoints
set logscale y

plot [0:340] [:1800] \
    cactus("fASP_conj") title "fASP-c" lc rgb "green",\
    cactus("fASP_src")  title "fASP-s" lc rgb "skyblue",\
    cactus("Hybrid_BMSA") title "H.E." lc rgb "dark-green",\
    cactus("PFVS") title "PFVS" lc rgb "black"