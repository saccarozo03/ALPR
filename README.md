#  Vehicle License Plate Recognition System 


 Graduation Thesis Project — Hanoi University of Science and Technology (HUST)  
Major: Mechatronics Engineering (Advanced Program)

---

##  Project Overview

This project focuses on building a **real-time Vehicle License Plate Recognition (VLPR)** system using **Deep Learning-based Computer Vision**.

The system performs:

- License plate detection  
- Plate region extraction  
- Character recognition (OCR)  
- Deployment on embedded edge devices (Raspberry Pi / RockPi)

The goal is to provide a practical AI solution for **smart transportation** and **industrial applications**.

---

##  Key Features

 Real-time license plate detection using YOLO-based models  
 OCR pipeline for character recognition (PaddleOCR / VietOCR)  
 End-to-end training workflow: dataset → labeling → training → inference  
 Embedded deployment on resource-constrained devices  
 Modular design for industrial integration

---

## System Architecture

```text
Input Video/Camera
        ↓
License Plate Detection (YOLO)
        ↓
Plate Cropping & Preprocessing
        ↓
OCR Recognition (Deep Learning)
        ↓
Text Output + Coordinate Export
