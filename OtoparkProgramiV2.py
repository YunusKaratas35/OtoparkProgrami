import cv2
import cv2.aruco as aruco
import pytesseract
import tkinter as tk
from tkinter import ttk
import time
import random
import serial
import serial.tools.list_ports
import threading

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class AracParkUygulamasi:
    def __init__(self, root):
        self.root = root
        self.root.title("Arac Park Uygulamasi")
        self.root.quit_flag = threading.Event()
        self.araclarin_listesi = {}
        self.max_arac_sayisi = 9
        self.uart = None
        self.cooldown = {}
        self.reset_handler = None
        self.mode = 'aruco'

        self.create_widgets()

        self.root.protocol("WM_DELETE_WINDOW", self.kapat_program)

        self.aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_6X6_1000)
        self.parameters = aruco.DetectorParameters()

        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

        self.scan_com_ports()
        self.root.after(5000, self.update_com_ports)

        self.aruco_thread = threading.Thread(target=self.detect_aruco)
        self.aruco_thread.start()

    def create_widgets(self):
        self.isim_label = tk.Label(self.root, text="Lutfen adinizi giriniz:")
        self.isim_label.pack(pady=10)
        self.isim_entry = tk.Entry(self.root)
        self.isim_entry.pack(pady=10)

        self.giris_button = tk.Button(self.root, text="Giris Yap", command=self.giris_yap)
        self.giris_button.pack(pady=10)

        self.fis_no_label = tk.Label(self.root, text="Fis numarasini giriniz:")
        self.fis_no_label.pack(pady=10)
        self.fis_no_entry = tk.Entry(self.root)
        self.fis_no_entry.pack(pady=10)

        self.cikis_button = tk.Button(self.root, text="Cikis Yap", command=lambda: self.cikis_yap_manuel())
        self.cikis_button.pack(pady=10)

        self.kapat_button = tk.Button(self.root, text="Programi Kapat", command=self.kapat_program)
        self.kapat_button.pack(pady=10)

        self.mode_button = tk.Button(self.root, text="Modu Degistir", command=self.change_mode)
        self.mode_button.pack(pady=10)

        self.sonuc_label = tk.Label(self.root, text="")
        self.sonuc_label.pack(pady=10)

        self.arac_bilgileri_label = tk.Label(self.root, text="Icerdeki Araclar:")
        self.arac_bilgileri_label.pack(pady=10)
        self.arac_bilgileri_text = tk.Text(self.root, height=10, width=50)
        self.arac_bilgileri_text.pack(pady=10)
        self.update_arac_bilgileri()

        self.ayarlar_frame = tk.Frame(self.root)
        self.ayarlar_frame.pack(anchor='ne', padx=10, pady=10)

        self.ayarlar_button = tk.Button(self.ayarlar_frame, text="Ayarlar", command=self.ayarlar_penceresi)
        self.ayarlar_button.pack(side='left')

        self.stm_status_label = tk.Label(self.ayarlar_frame, text="STM Bagli Degil")
        self.stm_status_label.pack(side='left', padx=10)

    def change_mode(self):
        if self.mode == 'aruco':
            self.mode = 'Rakam'
        else:
            self.mode = 'aruco'
        self.sonuc_label.config(text=f"Mevcut mod: {self.mode}")

    def detect_aruco(self):
        try:
            while not self.root.quit_flag.is_set():
                ret, frame = self.cap.read()
                if not ret:
                    continue

                rect_x = 200
                rect_y = 150
                rect_w = 200
                rect_h = 200
                roi = frame[rect_y:rect_y + rect_h, rect_x:rect_x + rect_w]

                if self.mode == 'aruco':
                    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                    corners, ids, rejected_img_points = aruco.detectMarkers(gray, self.aruco_dict, parameters=self.parameters)
                    roi = aruco.drawDetectedMarkers(roi, corners, ids)
                else:
                    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                    custom_config = r'--oem 3 --psm 6 outputbase digits'
                    data = pytesseract.image_to_data(gray, config=custom_config, output_type=pytesseract.Output.DICT)

                    n_boxes = len(data['level'])
                    detected_digits = ""

                    for i in range(n_boxes):
                        if data['text'][i].isdigit():
                            (x, y, w, h) = (data['left'][i], data['top'][i], data['width'][i], data['height'][i])
                            roi = cv2.rectangle(roi, (x, y), (x + w, y + h), (0, 255, 0), 2)
                            detected_digits += data['text'][i]

                    if detected_digits.isdigit() and int(detected_digits) in self.araclarin_listesi:
                        fis_no = int(detected_digits)
                        if fis_no not in self.cooldown or time.time() - self.cooldown[fis_no] > 5:
                            self.cikis_yap(fis_no)

                    cv2.putText(frame, f'Detected Digits: {detected_digits}', (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

                cv2.rectangle(frame, (rect_x, rect_y), (rect_x + rect_w, rect_y + rect_h), (255, 0, 0), 2)
                cv2.imshow('Digit Detection', frame)

                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            self.cap.release()
            cv2.destroyAllWindows()

    def scan_com_ports(self):
        self.ports = list(serial.tools.list_ports.comports())
        self.port_names = [port.device for port in self.ports]

    def update_com_ports(self):
        old_ports = set(self.port_names)
        self.scan_com_ports()
        new_ports = set(self.port_names)
        if old_ports != new_ports:
            self.com_port_menu['values'] = self.port_names
            self.com_port_var.set(self.port_names[0] if self.port_names else "")
        self.stm_status_label.config(text="STM Bagli" if self.uart else "STM Bagli Degil")
        self.root.after(5000, self.update_com_ports)

    def ayarlar_penceresi(self):
        ayarlar_penceresi = tk.Toplevel(self.root)
        ayarlar_penceresi.title("Ayarlar")

        com_label = tk.Label(ayarlar_penceresi, text="COM Port:")
        com_label.pack(pady=10)

        self.com_port_var = tk.StringVar(ayarlar_penceresi)
        self.com_port_var.set(self.port_names[0] if self.port_names else "")

        self.com_port_menu = ttk.Combobox(ayarlar_penceresi, textvariable=self.com_port_var, values=self.port_names)
        self.com_port_menu.pack(pady=10)

        baglanti_button = tk.Button(ayarlar_penceresi, text="Baglan", command=self.baglan)
        baglanti_button.pack(pady=10)

    def baglan(self):
        com_port = self.com_port_var.get()
        if com_port:
            try:
                self.uart = serial.Serial(port=com_port, baudrate=115200, timeout=1)
                self.sonuc_label.config(text=f"Baglanti kuruldu: {com_port}")
                self.stm_status_label.config(text="STM Bagli")
            except serial.SerialException as e:
                self.sonuc_label.config(text=f"Baglanti hatasi: {e}")
                self.stm_status_label.config(text="STM Bagli Degil")

    def giris_yap(self):
        if len(self.araclarin_listesi) < self.max_arac_sayisi:
            giris = time.time()
            arac_sahibi = self.isim_entry.get()
            if arac_sahibi:
                while True:
                    fis_no = random.randint(1, 9)
                    if fis_no not in self.araclarin_listesi:
                        break
                self.araclarin_listesi[fis_no] = {"giris": giris, "sahibi": arac_sahibi}
                self.sonuc_label.config(text=f"{fis_no} numarali arac giris yapti.")
                self.isim_entry.delete(0, tk.END)
                self.update_arac_bilgileri()
        else:
            self.sonuc_label.config(text="Maksimum arac sayisina ulasildi!")

    def cikis_yap(self, fis_no):
        if fis_no in self.araclarin_listesi:
            cikis = time.time()
            giris = self.araclarin_listesi[fis_no]["giris"]
            arac_sahibi = self.araclarin_listesi[fis_no]["sahibi"]
            toplam_sure = cikis - giris
            toplam_fiyat = toplam_sure * 60

            self.sonuc_label.config(text=f"{fis_no} numarali arac icin gecen sure {toplam_sure:.2f} saniye, odenecek tutar {toplam_fiyat:.2f} TL. Gule gule {arac_sahibi}.")
            if self.uart:
                try:
                    self.uart.write(str(fis_no).encode())
                    print("Cikis yapan fis numarasi:", fis_no)
                except serial.SerialException:
                    self.sonuc_label.config(text="UART baglantisi basarisiz. Veriler gonderilemedi.")

            del self.araclarin_listesi[fis_no]
            self.update_arac_bilgileri()

            if self.uart:
                if self.reset_handler is not None:
                    self.root.after_cancel(self.reset_handler)
                self.reset_handler = self.root.after(5000, lambda: self.uart.write('C'.encode()))

            self.cooldown[fis_no] = time.time()
        else:
            self.sonuc_label.config(text="Bu fis numarasi ile arac bulunamadi.")

    def cikis_yap_manuel(self):
        fis_no = self.fis_no_entry.get()
        if fis_no.isdigit():
            self.cikis_yap(int(fis_no))
            self.fis_no_entry.delete(0, tk.END)
        else:
            self.sonuc_label.config(text="Gecerli bir fis numarasi giriniz.")

    def kapat_program(self):
        self.root.quit_flag.set()
        try:
            if self.uart:
                try:
                    self.uart.write('C'.encode())
                    self.uart.close()
                except serial.SerialException:
                    self.sonuc_label.config(text="UART baglantisi basarisiz.")

            if self.cap.isOpened():
                self.cap.release()

            self.aruco_thread.join(timeout=1)

            cv2.destroyAllWindows()
        except Exception as e:
            print(f"Program kapanirken bir hata olustu: {e}")
        finally:
            self.root.destroy()

    def update_arac_bilgileri(self):
        self.arac_bilgileri_text.delete(1.0, tk.END)
        for fis_no, bilgiler in self.araclarin_listesi.items():
            arac_bilgisi = f"Fis No: {fis_no}, Sahibi: {bilgiler['sahibi']}\n"
            self.arac_bilgileri_text.insert(tk.END, arac_bilgisi)

if __name__ == "__main__":
    root = tk.Tk()
    app = AracParkUygulamasi(root)
    root.mainloop()
    