set datafile separator ','
set terminal png
set output 'values.png'
set title "Fit real measured PV data to gaussian-function" 
set xlabel "Time in 5 minute slots" 
set ylabel "Produced Energy in Wh" 
set xrange [-1:280]
set yrange [-1:180]
x_0 = 150

simplegauss(x) = a*exp(-((x-x_0)/s)**2)
fit simplegauss(x) 'real-production-data.csv' using 0:1 via a, x_0, s
plot 'real-production-data.csv' using 0:1, simplegauss(x)
