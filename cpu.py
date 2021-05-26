import pyrtl
from pyrtl.wire import Const

# Initialize your memblocks here: 
i_mem = pyrtl.MemBlock(32, 32, 'i_mem', asynchronous = False)
d_mem = pyrtl.MemBlock(32, 32, 'd_mem', asynchronous = True)
rf = pyrtl.MemBlock(32, 32, 'rf', asynchronous = True)

pc = pyrtl.Register(32, 'pc')
# When working on large designs, such as this CPU implementation, it is
# useful to partition your design into smaller, reusable, hardware
# blocks. In PyRTL, one way to do this is through functions. Here are 
# some examples of hardware blocks that can help you get started on this
# CPU design. You may have already worked on this logic in prior labs.

def decode(instr, op, rs, rt, rd, func, imm):

   op <<= instr[26:32]
   rs <<= instr[21:26]
   rt <<= instr[16:21]
   rd <<= instr[11:16]
   func <<= instr[0:6]
   imm <<= instr[0:16]

   return op, rs, rt, rd, func, imm

def alu(data0, data1, aluop, zero, alu_out):
   
   with pyrtl.conditional_assignment:
      with aluop == 0x0:
         alu_out |= data0 + data1
      with aluop == 0x1:
         alu_out |= data0 & data1
      with aluop == 0x2:
         alu_out |= data0 + data1
      with aluop == 0x3:
         alu_out |= pyrtl.shift_left_logical(data1, Const(16))
      with aluop == 0x4:
         alu_out |= data0 | data1
      with aluop == 0x5:
         alu_out |= pyrtl.signed_lt(data0, data1)
      with aluop == 0x6:
         alu_out |= data0 + data1
      with aluop == 0x7:
         alu_out|= data0 + data1
      with data0 == data1:
         zero |= 1

   return zero, alu_out

def controller(op, func, reg_dst, branch, regwrite, alu_src, mem_write, mem_to_reg, alu_op):
   control_signals = pyrtl.WireVector(10, 'signals')
   with pyrtl.conditional_assignment:
      with op == 0:
         with func == 0x20: #ADD
            control_signals |= 0x280
         with func == 0x24: #AND
            control_signals |= 0x281
         with func == 0x2A: #SLT
            control_signals |= 0x285
      with op == 0x8: #ADDI
         control_signals |= 0x0A2 
      with op == 0xF: #LUI
         control_signals |= 0x0A3 
      with op == 0xD: #ORI
         control_signals |= 0x0A4 
      with op == 0x23: #LW
         control_signals |= 0x2AE
      with op == 0x2B: #SW
         control_signals |= 0x237
      with op == 0x4: #BEQ
         control_signals |= 0x100
   
   reg_dst <<= control_signals[9]
   branch <<= control_signals[8]
   regwrite <<= control_signals[7]
   alu_src <<= control_signals[5:7]
   mem_write <<= control_signals[4]
   mem_to_reg <<= control_signals[3]
   alu_op <<= control_signals[0:3]

   return reg_dst, branch, regwrite, alu_src, mem_write, mem_to_reg, alu_op

'''
def reg_read():
   raise NotImplementedError
'''
def pc_update(branch_and, imm_ext):
   with pyrtl.conditional_assignment:
      with branch_and:
         pc.next |= pc + 1 + imm_ext
      with pyrtl.otherwise:
         pc.next |= pc + 1
   #raise NotImplementedError

def write_back(rf_write, alu_out, data1, mem_to_reg, mem_write, regwrite):
   #To fix the exceed write port on rf, make it so that you only write once, but the addr changes depending on mem_to_reg
   data_to_reg = pyrtl.WireVector(32, 'data_to_reg')
   with pyrtl.conditional_assignment:
      with mem_to_reg:
         data_to_reg |= d_mem[alu_out]
      with pyrtl.otherwise:
         data_to_reg |= alu_out
   
   with pyrtl.conditional_assignment:
      with mem_write:
         d_mem[alu_out] |= pyrtl.MemBlock.EnabledWrite(data1, 1)
      with regwrite:
         with rf_write != 0:
            rf[rf_write] |= pyrtl.MemBlock.EnabledWrite(data_to_reg, 1)
   #raise NotImplementedError

# These functions implement smaller portions of the CPU design. A 
# top-level function is required to bring these smaller portions
# together and finish your CPU design. Here you will instantiate 
# the functions, i.e., build hardware, and orchestrate the various 
# parts of the CPU together. 

def top():
   instruction = pyrtl.WireVector(32, 'instr')
   instruction <<= i_mem[pc]
   
   op = pyrtl.WireVector(bitwidth=6, name='op')
   rs = pyrtl.WireVector(bitwidth=5, name='rs')
   rt = pyrtl.WireVector(bitwidth=5, name='rt')
   rd = pyrtl.WireVector(bitwidth=5, name='rd')
   func = pyrtl.WireVector(bitwidth=6, name='func')
   imm = pyrtl.WireVector(bitwidth=16, name='imm')
   imm_ext = pyrtl.WireVector(32, 'imm_ext')

   op, rs, rt, rd, func, imm = decode(instruction, op, rs, rt, rd, func, imm)
   imm_ext <<= imm.sign_extended(32)

   reg_dst = pyrtl.WireVector(1, 'reg_dst')
   branch = pyrtl.WireVector(1, 'branch')
   regwrite = pyrtl.WireVector(1, 'regwrite')
   alu_src = pyrtl.WireVector(2, 'alu_src')
   mem_write = pyrtl.WireVector(1, 'mem_write')
   mem_to_reg = pyrtl.WireVector(1, 'mem_to_reg')
   alu_op = pyrtl.WireVector(3, 'alu_op')

   reg_dst, branch, regwrite, alu_src, mem_write, mem_to_reg, alu_op = controller(op, func, reg_dst, branch, regwrite, alu_src, mem_write, mem_to_reg, alu_op)

   rf_write = pyrtl.WireVector(5, 'rf_write')
   with pyrtl.conditional_assignment:
      with reg_dst == 0:
         rf_write |= rt
      with pyrtl.otherwise:
         rf_write |= rd

   data0 = pyrtl.WireVector(bitwidth=32, name = 'data0')
   data1 = pyrtl.WireVector(bitwidth=32, name = 'data1')
   alu_in1 = pyrtl.WireVector(32, name = 'alu_in1')

   #Write more code to check to see if you are writing to the 0 register or not.

   data0 <<= rf[rs]
   data1 <<= rf[rt]

   with pyrtl.conditional_assignment:
      with alu_src == 0:
         alu_in1 |= data1
      with pyrtl.otherwise:
         alu_in1 |= imm_ext
   
   zero = pyrtl.WireVector(1, 'zero')
   alu_out = pyrtl.WireVector(32, 'alu_out')

   zero, alu_out = alu(data0, alu_in1, alu_op, zero, alu_out)

   write_back(rf_write, alu_out, data1, mem_to_reg, mem_write, regwrite)

   branch_and = pyrtl.WireVector(1, 'branch_and')
   branch_and <<= zero & branch

   pc_update(branch_and, imm_ext)

   #raise NotImplementedError

if __name__ == '__main__':
   top()
   """

    Here is how you can test your code.
    This is very similar to how the autograder will test your code too.

    1. Write a MIPS program. It can do anything as long as it tests the
       instructions you want to test.

    2. Assemble your MIPS program to convert it to machine code. Save
       this machine code to the "i_mem_init.txt" file.
       You do NOT want to use QtSPIM for this because QtSPIM sometimes
       assembles with errors. One assembler you can use is the following:

       https://alanhogan.com/asu/assembler.php

    3. Initialize your i_mem (instruction memory).

    4. Run your simulation for N cycles. Your program may run for an unknown
       number of cycles, so you may want to pick a large number for N so you
       can be sure that the program so that all instructions are executed.

    5. Test the values in the register file and memory to make sure they are
       what you expect them to be.

    6. (Optional) Debug. If your code didn't produce the values you thought
       they should, then you may want to call sim.render_trace() on a small
       number of cycles to see what's wrong. You can also inspect the memory
       and register file after every cycle if you wish.

    Some debugging tips:

        - Make sure your assembly program does what you think it does! You
          might want to run it in a simulator somewhere else (SPIM, etc)
          before debugging your PyRTL code.

        - Test incrementally. If your code doesn't work on the first try,
          test each instruction one at a time.

        - Make use of the render_trace() functionality. You can use this to
          print all named wires and registers, which is extremely helpful
          for knowing when values are wrong.

        - Test only a few cycles at a time. This way, you don't have a huge
          500 cycle trace to go through!

   """
   
   #Start a simulation trace
   sim_trace = pyrtl.SimulationTrace()

   # Initialize the i_mem with your instructions.
   i_mem_init = {}
   with open('i_mem_init3.txt', 'r') as fin:
        i = 0
        for line in fin.readlines():
            i_mem_init[i] = int(line, 16)
            i += 1

   sim = pyrtl.Simulation(tracer=sim_trace, memory_value_map={
         i_mem : i_mem_init
   })

   # Run for an arbitrarily large number of cycles.
   for cycle in range(1):
      sim.step({})

    # Use render_trace() to debug if your code doesn't work.
    # sim_trace.render_trace()
   
   sim_trace.render_trace(symbol_len=10)

    # You can also print out the register file or memory like so if you want to debug:
   print(sim.inspect_mem(d_mem))
   print(sim.inspect_mem(rf))

    # Perform some sanity checks to see if your program worked correctly
   #assert(sim.inspect_mem(d_mem)[0] == 10)
   #assert(sim.inspect_mem(rf)[8] == 10)    # $v0 = rf[8]
   print('Passed!')
