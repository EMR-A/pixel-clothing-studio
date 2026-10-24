// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Pixel Clothing Studio contributors
using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;
class Launcher {
    [STAThread] static void Main() {
        string root=AppDomain.CurrentDomain.BaseDirectory;
        string exe=Path.Combine(root,"python","pythonw.exe");
        string app=Path.Combine(root,"source","app.pyw");
        if (!File.Exists(exe) || !File.Exists(app)) {
            MessageBox.Show("ZIP dosyasının tamamını bir klasöre çıkarın; yalnızca EXE dosyasını taşımayın.","Pixel Clothing Studio"); return;
        }
        ProcessStartInfo info=new ProcessStartInfo(exe,"\""+app+"\"");
        info.WorkingDirectory=root;info.UseShellExecute=false;info.CreateNoWindow=true;
        info.EnvironmentVariables["PYTHONNOUSERSITE"]="1";
        try { Process.Start(info); }
        catch (Exception error) { MessageBox.Show(error.Message,"Pixel Clothing Studio"); }
    }
}
