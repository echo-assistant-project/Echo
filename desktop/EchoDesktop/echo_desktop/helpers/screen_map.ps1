# EchoDesktop screen map (computer use): one look at the primary screen, printed as JSON.
#   elements: buttons, fields, links, menu items... of the active window (Windows UI Automation), with positions
#   text:     every line of text on screen (Windows OCR), with positions
#   image:    the screenshot as a small JPEG (base64) for AI models that can see images (only with -Image)
# All coordinates are physical screen pixels (this script is DPI-aware). The screenshot is written to a temporary
# file for OCR and deleted immediately. Runs only during a computer-use task the user started.
param([long]$Hwnd = 0, [switch]$Image, [int]$MaxSide = 1280)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type @'
using System; using System.Runtime.InteropServices;
public static class EchoWin {
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern int GetSystemMetrics(int i);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, System.Text.StringBuilder s, int n);
}
'@
[void][EchoWin]::SetProcessDPIAware()
Add-Type -AssemblyName System.Drawing, System.Runtime.WindowsRuntime, UIAutomationClient, UIAutomationTypes

$w = [EchoWin]::GetSystemMetrics(0); $h = [EchoWin]::GetSystemMetrics(1)
$bitmap = New-Object System.Drawing.Bitmap $w, $h
$g = [System.Drawing.Graphics]::FromImage($bitmap)
$g.CopyFromScreen(0, 0, 0, 0, (New-Object System.Drawing.Size $w, $h))
$g.Dispose()

$out = [ordered]@{ screen = @{ w = $w; h = $h }; window = ''; elements = @(); text = @(); image = $null; scale = 1.0 }

# ---- UI Automation: interactive elements of the active window
$target = if ($Hwnd -ne 0) { [IntPtr]$Hwnd } else { [EchoWin]::GetForegroundWindow() }
try {
  $sb = New-Object System.Text.StringBuilder 256
  [void][EchoWin]::GetWindowText($target, $sb, 256); $out.window = $sb.ToString()
  $root = [System.Windows.Automation.AutomationElement]::FromHandle($target)
  $A = [System.Windows.Automation.AutomationElement]; $T = [System.Windows.Automation.ControlType]
  $types = @($T::Button, $T::Edit, $T::Hyperlink, $T::MenuItem, $T::ListItem, $T::TabItem, $T::CheckBox, $T::RadioButton,
             $T::ComboBox, $T::TreeItem, $T::SplitButton, $T::Document, $T::MenuBar, $T::Slider)
  $conds = $types | ForEach-Object { New-Object System.Windows.Automation.PropertyCondition($A::ControlTypeProperty, $_) }
  $or = New-Object System.Windows.Automation.OrCondition(([System.Windows.Automation.Condition[]]$conds))
  $on = New-Object System.Windows.Automation.PropertyCondition($A::IsOffscreenProperty, $false)
  $and = New-Object System.Windows.Automation.AndCondition($or, $on)
  $found = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, $and)
  $list = New-Object System.Collections.ArrayList
  foreach ($e in $found) {
    if ($list.Count -ge 160) { break }
    $c = $e.Current; $r = $c.BoundingRectangle
    if ($r.IsEmpty -or $r.Width -lt 4 -or $r.Height -lt 4 -or $r.X -lt -10 -or $r.Y -lt -10 -or $r.X -gt $w -or $r.Y -gt $h) { continue }
    $name = $c.Name; if ($name.Length -gt 80) { $name = $name.Substring(0, 80) }
    $value = ''
    if (-not $c.IsPassword) {   # a password field's contents are never read
      try { $vp = $e.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern); $value = $vp.Current.Value } catch {}
    }
    if ($value.Length -gt 60) { $value = $value.Substring(0, 60) }
    [void]$list.Add([ordered]@{ type = $c.ControlType.ProgrammaticName.Replace('ControlType.', ''); name = $name; value = $value;
                               x = [int]$r.X; y = [int]$r.Y; w = [int]$r.Width; h = [int]$r.Height;
                               password = [bool]$c.IsPassword; enabled = [bool]$c.IsEnabled })
  }
  $out.elements = $list
} catch { $out.window = $out.window + ' (UI Automation unavailable)' }

# ---- OCR: text lines with positions
$path = Join-Path ([IO.Path]::GetTempPath()) ('echo-map-' + [Guid]::NewGuid().ToString('N') + '.png')
$bitmap.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
try {
  $null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
  $null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime]
  $null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
  $asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
      $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
  function Await($op, [Type]$t) { $task = $asTask.MakeGenericMethod($t).Invoke($null, @($op)); $task.Wait(-1) | Out-Null; $task.Result }
  $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($path)) ([Windows.Storage.StorageFile])
  $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
  $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
  $soft = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
  $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
  if ($engine) {
    $res = Await ($engine.RecognizeAsync($soft)) ([Windows.Media.Ocr.OcrResult])
    $lines = New-Object System.Collections.ArrayList
    foreach ($line in $res.Lines) {
      if ($lines.Count -ge 220) { break }
      $x1 = 1e9; $y1 = 1e9; $x2 = 0; $y2 = 0
      foreach ($wd in $line.Words) { $b = $wd.BoundingRect
        $x1 = [Math]::Min($x1, $b.X); $y1 = [Math]::Min($y1, $b.Y); $x2 = [Math]::Max($x2, $b.X + $b.Width); $y2 = [Math]::Max($y2, $b.Y + $b.Height) }
      $t = $line.Text; if ($t.Length -gt 100) { $t = $t.Substring(0, 100) }
      [void]$lines.Add([ordered]@{ text = $t; x = [int]$x1; y = [int]$y1; w = [int]($x2 - $x1); h = [int]($y2 - $y1) })
    }
    $out.text = $lines
  }
  $stream.Dispose()
} catch {} finally { Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue }

# ---- small JPEG for vision models
if ($Image) {
  $scale = [Math]::Min(1.0, $MaxSide / [Math]::Max($w, $h))
  $sw = [int]($w * $scale); $sh = [int]($h * $scale)
  $small = New-Object System.Drawing.Bitmap $sw, $sh
  $g2 = [System.Drawing.Graphics]::FromImage($small)
  $g2.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
  $g2.DrawImage($bitmap, 0, 0, $sw, $sh); $g2.Dispose()
  $codec = [System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() | Where-Object { $_.MimeType -eq 'image/jpeg' }
  $ep = New-Object System.Drawing.Imaging.EncoderParameters 1
  $ep.Param[0] = New-Object System.Drawing.Imaging.EncoderParameter([System.Drawing.Imaging.Encoder]::Quality, [long]70)
  $ms = New-Object System.IO.MemoryStream
  $small.Save($ms, $codec, $ep); $small.Dispose()
  $out.image = [Convert]::ToBase64String($ms.ToArray()); $out.scale = $scale
}
$bitmap.Dispose()
[Console]::Out.WriteLine(($out | ConvertTo-Json -Depth 5 -Compress))
