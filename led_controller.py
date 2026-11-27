# code for LED setup (no arduino yet just for testing purposes)


import tkinter as tk

# defined for the UI
class LEDController:

    def __init__(self, parent):
        self.canvas = tk.Canvas(
            parent,
            width=350,
            height=125,
            bg="#242424",
            highlightthickness=0
        )

        # Green LED
        self.green_led = self.canvas.create_oval(
            40, 25, 115, 100,
            fill="gray",
            outline="black"
        )

        # Red LED
        self.red_led = self.canvas.create_oval(
            220, 25, 295, 100,
            fill="gray",
            outline="black"
        )

    def show(self):
        self.canvas.pack()

    def access_granted(self):
        self.canvas.itemconfig(self.green_led, fill="green")
        self.canvas.itemconfig(self.red_led, fill="gray")

    def access_denied(self):
        self.canvas.itemconfig(self.green_led, fill="gray")
        self.canvas.itemconfig(self.red_led, fill="red")

    def reset(self):
        self.canvas.itemconfig(self.green_led, fill="gray")
        self.canvas.itemconfig(self.red_led, fill="gray")


#result = process_image_frame(frame)

#if result:
    #led_controller.access_granted()
#else:
    #led_controller.access_denied()
