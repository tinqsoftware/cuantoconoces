// Lanzador del archivo portable de Quiz Studio.
// Compilar con .NET Framework 4.x (incluido en GitHub Actions para Windows).
// El ZIP agregado al final del .exe contiene runtime/ y data/.

using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Text;
using System.Windows.Forms;

internal static class PortableLauncher
{
    private const string MagicText = "QUIZSTUDIO_PORTABLE_V1";
    private const int MagicSize = 32;
    private const int FooterSize = MagicSize + 8 + 32;

    [STAThread]
    private static void Main()
    {
        try
        {
            string container = Assembly.GetExecutingAssembly().Location;
            bool showFileAfterClose = false;
            if (!CanUpdateInPlace(container))
            {
                container = CopyToSafeFolder(container);
                showFileAfterClose = true;
            }

            long payloadStart = ReadPayloadStart(container);
            string bundle = Path.Combine(Path.GetTempPath(), "QuizStudioPortable-" + Guid.NewGuid().ToString("N"));
            string archive = Path.Combine(bundle, "payload.zip");
            Directory.CreateDirectory(bundle);
            CopyPayload(container, payloadStart, archive);
            ZipFile.ExtractToDirectory(archive, bundle);
            File.Delete(archive);

            string runtime = Path.Combine(bundle, "runtime", "Quiz Studio.exe");
            if (!File.Exists(runtime))
                throw new InvalidDataException("No se encontró el programa dentro del archivo portable.");

            string data = Path.Combine(bundle, "data");
            Directory.CreateDirectory(data);
            ProcessStartInfo start = new ProcessStartInfo(runtime);
            start.WorkingDirectory = bundle;
            start.UseShellExecute = false;
            start.EnvironmentVariables["QUIZ_STUDIO_PORTABLE_ROOT"] = data;
            start.EnvironmentVariables["QUIZ_STUDIO_PORTABLE_BUNDLE"] = bundle;
            start.EnvironmentVariables["QUIZ_STUDIO_PORTABLE_CONTAINER"] = container;
            start.EnvironmentVariables["QUIZ_STUDIO_PORTABLE_SHOW_FILE"] = showFileAfterClose ? "1" : "0";
            Process.Start(start);
        }
        catch (Exception error)
        {
            MessageBox.Show(
                "No se pudo abrir este archivo portable.\n\n" + error.Message,
                "Quiz Studio",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error
            );
        }
    }

    private static long ReadPayloadStart(string container)
    {
        FileInfo info = new FileInfo(container);
        if (info.Length < FooterSize)
            throw new InvalidDataException("El archivo portable está incompleto.");
        byte[] footer = new byte[FooterSize];
        using (FileStream stream = File.OpenRead(container))
        {
            stream.Seek(-FooterSize, SeekOrigin.End);
            ReadExactly(stream, footer, footer.Length);
        }
        byte[] magic = Encoding.ASCII.GetBytes(MagicText);
        for (int index = 0; index < MagicSize; index++)
        {
            byte expected = index < magic.Length ? magic[index] : (byte)0;
            if (footer[index] != expected)
                throw new InvalidDataException("Este no parece ser un archivo portable de Quiz Studio.");
        }
        long payloadSize = BitConverter.ToInt64(footer, MagicSize);
        long start = info.Length - FooterSize - payloadSize;
        if (payloadSize <= 0 || start <= 0)
            throw new InvalidDataException("El paquete interno no es válido.");
        return start;
    }

    private static void CopyPayload(string sourcePath, long payloadStart, string archivePath)
    {
        using (FileStream source = File.OpenRead(sourcePath))
        using (FileStream destination = File.Create(archivePath))
        {
            source.Seek(payloadStart, SeekOrigin.Begin);
            byte[] buffer = new byte[1024 * 1024];
            long remaining = source.Length - FooterSize - payloadStart;
            while (remaining > 0)
            {
                int read = source.Read(buffer, 0, (int)Math.Min(buffer.Length, remaining));
                if (read == 0)
                    throw new EndOfStreamException("No se pudo leer el paquete interno.");
                destination.Write(buffer, 0, read);
                remaining -= read;
            }
        }
    }

    private static void ReadExactly(Stream stream, byte[] buffer, int count)
    {
        int offset = 0;
        while (offset < count)
        {
            int read = stream.Read(buffer, offset, count - offset);
            if (read == 0)
                throw new EndOfStreamException();
            offset += read;
        }
    }

    private static bool CanUpdateInPlace(string source)
    {
        try
        {
            string folder = Path.GetDirectoryName(source);
            if (String.IsNullOrEmpty(folder) || source.IndexOf(Path.GetTempPath(), StringComparison.OrdinalIgnoreCase) == 0)
                return false;
            string probe = Path.Combine(folder, ".quiz-studio-write-test-" + Guid.NewGuid().ToString("N"));
            using (File.Create(probe)) { }
            File.Delete(probe);
            return true;
        }
        catch
        {
            return false;
        }
    }

    private static string CopyToSafeFolder(string source)
    {
        string documents = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);
        string folder = Path.Combine(documents, "Quiz Studio", "Juegos portátiles");
        Directory.CreateDirectory(folder);
        string destination = Path.Combine(folder, Path.GetFileName(source));
        if (!File.Exists(destination) || !FilesMatch(source, destination))
            File.Copy(source, destination, true);
        return destination;
    }

    private static bool FilesMatch(string first, string second)
    {
        try
        {
            FileInfo one = new FileInfo(first);
            FileInfo two = new FileInfo(second);
            return one.Length == two.Length && one.LastWriteTimeUtc == two.LastWriteTimeUtc;
        }
        catch
        {
            return false;
        }
    }
}
