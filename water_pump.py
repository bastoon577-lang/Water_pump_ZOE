#!/usr/bin/env python3           
import argparse
import logging
import serial
import time
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from serial.tools import list_ports

def parse_arguments():
    p = argparse.ArgumentParser(description="Lecture / Reset WEP Renault Zoe (Mode lecture par défaut)")
    p.add_argument("-p","--port",default="COM3",help="permet de choisir le port COM")
    p.add_argument("-b","--baudrate",type=int,default=38400,help="permet de choisir la vitesse de communication")
    p.add_argument("-v","--verbosity",action="count",default=0,help="permet de choisir le niveau de verbosité")
    p.add_argument("-r","--reset",action="store_true",help="permet de reseter les compteurs")
    return p.parse_args()

def configure_logging(level):
    log_level = logging.WARNING
    if level == 1: log_level = logging.INFO
    elif level >= 2: log_level = logging.DEBUG
    logging.basicConfig(level=log_level,
                        format="%(asctime)s [%(levelname)s] %(message)s",
                        datefmt="%H:%M:%S")

def send_cmd(ser, cmd, wait=0.3):
    logging.debug(f"SÉRIE -> {cmd}")
    ser.write((cmd + "\r").encode())
    time.sleep(wait)
    response = b""
    while True:
        if ser.in_waiting:
            response += ser.read(ser.in_waiting)
            if b">" in response:
                break
        else:
            time.sleep(0.05)
    txt = response.decode(errors="ignore").strip()
    logging.debug(f"SÉRIE <- {txt}")
    return txt

def init_read(ser):
    send_cmd(ser,"ATZ"); time.sleep(1)
    send_cmd(ser,"ATE0")
    send_cmd(ser,"ATWS")
    send_cmd(ser,"ATSP6")
    send_cmd(ser,"ATSH7E4")

def init_reset(ser):
    send_cmd(ser,"ATZ"); time.sleep(1)
    send_cmd(ser,"ATE0")
    send_cmd(ser,"ATH1")
    send_cmd(ser,"ATS1")
    send_cmd(ser,"ATSP6")
    send_cmd(ser,"ATSH7E4")
    send_cmd(ser,"10C0")
    send_cmd(ser,"223349")

def decode_wep_response(response_str, cmd):
    lines=[l.strip() for l in response_str.split("\n") if l.strip()]
    target=f"62 {cmd[2:4]} {cmd[4:6]}".replace(" ","")
    for line in lines:
        clean=line.replace(" ","")
        if target in clean:
            idx=clean.find(target)+len(target)
            payload=clean[idx:]
            if len(payload)>=8:
                val=int(payload[:8],16)
                h=val//3600;m=(val%3600)//60;s=val%60
                return val,f"{h}h {m}m {s}s"
    return None,"Erreur"

def read_wep(ser, output=print):
    pids={"Low Speed WEP":"223349","Middle Speed WEP":"22334A","High Speed WEP":"22334B"}
    total=0; results={}
    for name,cmd in pids.items():
        sec,txt=decode_wep_response(send_cmd(ser,cmd),cmd)
        results[name]=(sec,txt)
        if sec is not None: total+=sec
    output("="*20+" RESULTATS ZOE "+"="*20)
    for name,(_,txt) in results.items():
        output(f"{name:<20} : {txt}")
    h=total//3600;m=(total%3600)//60
    output("-"*55)
    output(f"Temps total cumulé WEP : {h}h {m}m")
    output("="*55)

def reset_wep(ser, output=print):
    init_reset(ser)
    for c in ["2E334900000000","2E334A00000000","2E334B00000000"]:
        output(f"{c} -> {send_cmd(ser,c)}")

def run_cli(args):
    configure_logging(args.verbosity)
    ser=serial.Serial(args.port,args.baudrate,timeout=3)
    ser.reset_input_buffer(); ser.reset_output_buffer()
    try:
        if args.reset:
            reset_wep(ser)
        else:
            init_read(ser)
            read_wep(ser)
    finally:
        ser.close()

def launch_gui():
    root=tk.Tk()
    root.title("Renault Zoe Water Pump")
    root.geometry("800x500")

    top=ttk.Frame(root); top.pack(fill="x",padx=10,pady=10)
    ttk.Label(top,text="Port COM :").pack(side="left")

    ports=[p.device for p in list_ports.comports()]
    port_var=tk.StringVar(value=ports[0] if ports else "COM6")
    ttk.Combobox(top,textvariable=port_var,values=ports,width=12).pack(side="left",padx=5)

    out=tk.Text(root,bg="black",fg="white",insertbackground="white",state="disabled")
    out.pack(fill="both",expand=True,padx=10,pady=(0,10))

    def log(msg):
        out.config(state="normal")
        out.insert("end", str(msg)+"\n")
        out.see("end")
        out.config(state="disabled")

    def clear():
        out.config(state="normal")
        out.delete("1.0","end")
        out.config(state="disabled")

    def open_ser():
        s=serial.Serial(port_var.get(),38400,timeout=3)
        s.reset_input_buffer(); s.reset_output_buffer()
        return s

    def do_read():
        clear()
        try:
            ser=open_ser()
            init_read(ser)
            read_wep(ser, log)
            ser.close()
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def do_reset():
        if not messagebox.askyesno("Confirmation","Cette action va remettre à 0 les compteurs de pompe à eau.\n"
                                   "Souhaitez vous continuer ?"):
            return
        clear()
        try:
            ser=open_ser()
            reset_wep(ser, log)
            ser.close()
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    ttk.Button(top,text="Lire compteurs",command=do_read).pack(side="left",padx=10)
    ttk.Button(top,text="Reset compteurs",command=do_reset).pack(side="left")
    ttk.Button(top,text="Quitter",command=root.destroy).pack(side="right")
    root.mainloop()

if __name__ == "__main__":
    if len(sys.argv) == 1:
        """
            That script is built without --windowed so it's necessary to remove
            the console to be great and keep it in console mode !
        """
        if sys.platform == 'win32':
            import ctypes
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)
        launch_gui()
    else:
        run_cli(parse_arguments())
