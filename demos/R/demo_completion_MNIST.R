#demo_completion_MNIST.R
rm(list=ls())
graphics.off()
require(ggplot2)
source("GLFM_infer.R")
source("GLFM_complete.R")
source("GLFM_computePDF.R")
source("GLFM_plotPatterns.R")
datos_mninst <- read.csv(file="../../datasets/mnist_train_small_100.csv", header=TRUE,stringsAsFactors = FALSE, sep=",")
n_labels<-datos_mninst[,1]
Xauxi<-as.matrix(datos_mninst[,2:785],ncol=99,nrow= 784, byrow=TRUE)
Xfull<-matrix((Xauxi),nrow=784,ncol=99)
Xfull<-t(Xfull)
Xfull<-Xfull+1
perc_missing <- 0.3
missing_val <- -100
N<-dim(Xfull)[1]
D<-dim(Xfull)[2]
Cfull<-rep('n',D)
rand_mat<-matrix(runif(N*D), ncol=D, nrow=N)
mask_missings <- (rand_mat < perc_missing)
Xmiss <- Xfull
Xmiss[mask_missings] <- missing_val
data_mnist<-list("X"=Xmiss,"C"=Cfull)
param_names<-c("missing","s2B","alpha","Niter","maxK","bias","transf_dummie")
bias <- 0 
s2B <- 0.5      
alpha <- 10   
Niter <- 50   
maxK <- 100  
missing <- -100
transf_dummie<-FALSE
params<-list(missing,s2B,alpha,Niter,maxK,bias,transf_dummie)
names(params)<-param_names
output2<-GLFM_complete(data_mnist,list(c(),params))