"""Command-line and Windows desktop entry point; no game files are bundled."""
import argparse
import json
from pathlib import Path
import queue
import threading
from freecam.iso import build_iso, build_xbe
from freecam.laboratory import VERSION


def gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    window = tk.Tk()
    window.title('Azurik Debug Menu ' + VERSION)
    icon = Path(__file__).resolve().parent / 'assets' / 'studio.ico'
    if icon.is_file():
        try:
            window.iconbitmap(str(icon))
        except tk.TclError:
            pass
    window.geometry('720x520')
    window.minsize(680, 500)
    area = ttk.Frame(window, padding=24)
    area.pack(fill='both', expand=True)
    ttk.Label(area, text='Azurik · Debug Menu ' + VERSION, font=('Segoe UI', 18, 'bold')).pack(anchor='w')
    ttk.Label(area, text='PAL / Europe (En, Fr, De) · Native menu in English', font=('Segoe UI', 10)).pack(anchor='w', pady=(4, 18))
    ttk.Label(area, text='Sélectionnez votre ISO Xbox. Une nouvelle copie sera créée.\n'
              'Choose your Xbox ISO. The original file is preserved.').pack(anchor='w')
    ttk.Label(area, text='Blanc → A → B en 1 seconde : ouvrir / rouvrir le menu.\n'
              'White → A → B within 1 second: open / reopen the menu.\n'
              'Relâchez les boutons avant de recommencer. / Release all buttons to repeat.\n'
              'Alternative : L3 + START · Freecam : 4e entrée / 4th entry\n'
              'Freecam : Blanc / White = quitter / exit · Y = HUD',
              wraplength=650).pack(anchor='w', pady=15)
    ttk.Label(area, text='Inclus / Included: Freecam · Text boxes · Oracles · Game state keys',
              wraplength=650).pack(anchor='w', pady=(0, 12))
    status = tk.StringVar(value='Prêt / Ready')
    bar = ttk.Progressbar(area, maximum=100)
    bar.pack(fill='x', pady=(4, 8))
    ttk.Label(area, textvariable=status, wraplength=595).pack(anchor='w')
    events = queue.Queue()
    busy = False

    def create():
        nonlocal busy
        source = filedialog.askopenfilename(title='ISO / XISO Azurik', filetypes=[('Xbox ISO', '*.iso *.xiso')])
        if not source:
            return
        destination = filedialog.asksaveasfilename(title='Nouvelle ISO / New ISO',
            initialfile=Path(source).stem + '-Debug-Menu-' + VERSION + '.iso', defaultextension='.iso',
            filetypes=[('Xbox ISO', '*.iso')], confirmoverwrite=False)
        if not destination:
            return
        busy = True
        button.config(state='disabled')
        def worker():
            try:
                report = build_iso(source, destination, lambda value, text: events.put(('progress', value, text)))
                events.put(('done', destination, report))
            except Exception as error:
                events.put(('error', str(error)))
        threading.Thread(target=worker, daemon=True).start()

    def poll():
        nonlocal busy
        try:
            while True:
                event = events.get_nowait()
                if event[0] == 'progress':
                    bar['value'], status_value = event[1], event[2]
                    status.set(status_value)
                else:
                    busy = False
                    button.config(state='normal')
                    if event[0] == 'done':
                        bar['value'] = 100
                        status.set('ISO créée / ISO created')
                        messagebox.showinfo('Terminé / Done', event[1] + '\n\nRedémarrez le jeu avec cette nouvelle ISO, sans ancien instantané.\nCold-boot this new image without an old save state.\n\nVidez le cache du jeu si les changements restent absents.\nClear the game cache if changes do not appear.')
                    else:
                        status.set('Échec / Failed')
                        messagebox.showerror('Azurik', event[1])
        except queue.Empty:
            pass
        window.after(150, poll)

    def close():
        if busy:
            messagebox.showinfo('Azurik', 'Construction en cours. Attendez la fin.\nBuild in progress. Wait for completion.')
            return
        window.destroy()
    button = ttk.Button(area, text='Créer une nouvelle ISO / Create a new ISO', command=create)
    button.pack(anchor='w', pady=(18, 0))
    window.protocol('WM_DELETE_WINDOW', close)
    window.after(150, poll)
    window.mainloop()


def main():
    parser = argparse.ArgumentParser(description='Azurik PAL/EU native Debug Menu ' + VERSION)
    parser.add_argument('--version', action='version', version=VERSION)
    parser.add_argument('--input', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.input is None and args.output is None:
        gui()
        return
    if args.input is None or args.output is None:
        parser.error('--input and --output are required together')
    build = build_xbe if args.input.suffix.lower() == '.xbe' else build_iso
    try:
        report = build(args.input, args.output)
    except (ValueError, OSError) as error:
        parser.exit(1, str(error) + '\n')
    print(json.dumps({'output': str(args.output), 'report': report}, indent=2))


if __name__ == '__main__':
    main()
