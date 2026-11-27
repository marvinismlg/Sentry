# code for LED setup (no arduino yet just for testing purposes)


import tkinter as tk


class LEDController:

    def __init__(self, parent):
        self.canvas = tk.Canvas(
            parent,
            width=350,
            height=140,
            bg="#242424",
            highlightthickness=0
        )

        # Green LED
        self.green_led = self.canvas.create_oval(
            40, 25, 130, 115,
            fill="gray",
            outline="black"
        )

        # Red LED
        self.red_led = self.canvas.create_oval(
            220, 25, 310, 115,
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
import tkinter as tk

class LEDController:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Sentry LED Indicators")
        self.root.geometry("350x200")

        self.canvas = tk.Canvas(self.root, width=350, height=140)
        self.canvas.pack()

        # Green LED
        self.green_led = self.canvas.create_oval(
            40, 25, 130, 115,
            fill="gray",
            outline="black"
        )

        # Red LED
        self.red_led = self.canvas.create_oval(
            220, 25, 310, 115,
            fill="gray",
            outline="black"
        )


    def access_granted(self):
        self.canvas.itemconfig(self.green_led, fill="green")
        self.canvas.itemconfig(self.red_led, fill="gray")

    def access_denied(self):
        self.canvas.itemconfig(self.green_led, fill="gray")
        self.canvas.itemconfig(self.red_led, fill="red")

    def reset(self):
        self.canvas.itemconfig(self.green_led, fill="gray")
        self.canvas.itemconfig(self.red_led, fill="gray")

if __name__ == "__main__":
    led_controller = LEDController()

    # Test buttons
    tk.Button(
        led_controller.root,
        text="Access Granted",
        command=led_controller.access_granted
    ).pack()

    tk.Button(
        led_controller.root,
        text="Access Denied",
        command=led_controller.access_denied
    ).pack()

    tk.Button(
        led_controller.root,
        text="Reset",
        command=led_controller.reset
    ).pack()

    led_controller.root.mainloop()

#result = process_image_frame(frame)

#if result:
    #led_controller.access_granted()
#else:
    #led_controller.access_denied()
