def fib(n): 
    #10= 1+1+2+3+5
    pervious=0
    number =1
    for _ in range (n):
        temp=number
        number=number + pervious
        pervious=temp
    return number     

if __name__ == "__main__":
    print(fib(1))
