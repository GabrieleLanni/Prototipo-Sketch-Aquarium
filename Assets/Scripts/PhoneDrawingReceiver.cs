using System;
using System.Collections;
using System.IO;
using System.Linq;
using UnityEngine;

/// <summary>
/// Controlla periodicamente la cartella PhoneUploadServer/Processed e mostra
/// l'ultimo pesce ritagliato in uno SpriteRenderer.
/// </summary>
public sealed class PhoneDrawingReceiver : MonoBehaviour
{
    [Header("Riferimenti")]
    [SerializeField] private SpriteRenderer targetRenderer;

    [Header("Cartella dei pesci elaborati")]
    [Tooltip("Percorso relativo alla cartella principale del progetto Unity. Puoi anche inserire un percorso assoluto.")]
    [SerializeField] private string processedFolder = "PhoneUploadServer/Processed";

    [Header("Impostazioni")]
    [Min(0.2f)]
    [SerializeField] private float checkInterval = 1f;

    [Min(0.1f)]
    [SerializeField] private float maximumWorldSize = 8f;

    [SerializeField] private bool loadLatestImageOnStart = true;

    private string resolvedProcessedFolder;
    private string lastLoadedFile;
    private DateTime lastLoadedWriteTimeUtc;
    private Sprite runtimeSprite;
    private Texture2D runtimeTexture;
    private Coroutine monitorCoroutine;

    private void Awake()
    {
        ResolveProcessedFolder();
    }

    private void OnEnable()
    {
        monitorCoroutine = StartCoroutine(MonitorProcessedFolder());
    }

    private void OnDisable()
    {
        if (monitorCoroutine != null)
        {
            StopCoroutine(monitorCoroutine);
            monitorCoroutine = null;
        }
    }

    private void OnDestroy()
    {
        DestroyRuntimeAssets();
    }

    [ContextMenu("Risolvi e mostra percorso Processed")]
    private void ResolveProcessedFolder()
    {
        if (Path.IsPathRooted(processedFolder))
        {
            resolvedProcessedFolder = Path.GetFullPath(processedFolder);
        }
        else
        {
            string projectRoot = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
            resolvedProcessedFolder = Path.GetFullPath(Path.Combine(projectRoot, processedFolder));
        }

        Debug.Log($"[PhoneDrawingReceiver] Cartella controllata: {resolvedProcessedFolder}", this);
    }

    private IEnumerator MonitorProcessedFolder()
    {
        if (!loadLatestImageOnStart)
        {
            lastLoadedFile = FindLatestImage();
            lastLoadedWriteTimeUtc = GetLastWriteTimeUtc(lastLoadedFile);
        }

        WaitForSecondsRealtime wait = new WaitForSecondsRealtime(checkInterval);

        while (enabled)
        {
            string latestFile = FindLatestImage();
            DateTime latestWriteTimeUtc = GetLastWriteTimeUtc(latestFile);

            bool imageChanged = !string.IsNullOrEmpty(latestFile) &&
                                (latestFile != lastLoadedFile ||
                                 latestWriteTimeUtc != lastLoadedWriteTimeUtc);

            if (imageChanged)
            {
                if (TryLoadImage(latestFile))
                {
                    lastLoadedFile = latestFile;
                    lastLoadedWriteTimeUtc = latestWriteTimeUtc;
                }
            }

            yield return wait;
        }
    }

    private string FindLatestImage()
    {
        if (string.IsNullOrWhiteSpace(resolvedProcessedFolder))
        {
            ResolveProcessedFolder();
        }

        if (!Directory.Exists(resolvedProcessedFolder))
        {
            return null;
        }

        try
        {
            return Directory
                .EnumerateFiles(resolvedProcessedFolder, "fish_*.png")
                .OrderByDescending(File.GetLastWriteTimeUtc)
                .FirstOrDefault();
        }
        catch (Exception error)
        {
            Debug.LogWarning($"[PhoneDrawingReceiver] Impossibile leggere la cartella Processed: {error.Message}", this);
            return null;
        }
    }

    private bool TryLoadImage(string filePath)
    {
        if (targetRenderer == null)
        {
            Debug.LogError("[PhoneDrawingReceiver] Assegna il Target Renderer nell'Inspector.", this);
            return false;
        }

        try
        {
            byte[] imageBytes = File.ReadAllBytes(filePath);
            Texture2D newTexture = new Texture2D(2, 2, TextureFormat.RGBA32, false);

            if (!newTexture.LoadImage(imageBytes, false))
            {
                Destroy(newTexture);
                Debug.LogWarning($"[PhoneDrawingReceiver] Il file non e' un'immagine valida: {filePath}", this);
                return false;
            }

            newTexture.name = Path.GetFileNameWithoutExtension(filePath);
            newTexture.wrapMode = TextureWrapMode.Clamp;
            newTexture.filterMode = FilterMode.Bilinear;

            float pixelsPerUnit = Mathf.Max(newTexture.width, newTexture.height) / maximumWorldSize;
            Sprite newSprite = Sprite.Create(
                newTexture,
                new Rect(0f, 0f, newTexture.width, newTexture.height),
                new Vector2(0.5f, 0.5f),
                pixelsPerUnit
            );

            newSprite.name = newTexture.name;

            DestroyRuntimeAssets();
            runtimeTexture = newTexture;
            runtimeSprite = newSprite;
            targetRenderer.sprite = runtimeSprite;

            Debug.Log($"[PhoneDrawingReceiver] Pesce caricato: {Path.GetFileName(filePath)}", this);
            return true;
        }
        catch (IOException)
        {
            // Il server potrebbe stare ancora completando il salvataggio.
            // Il file verra' riprovato al controllo successivo.
            return false;
        }
        catch (Exception error)
        {
            Debug.LogWarning($"[PhoneDrawingReceiver] Errore nel caricamento di {filePath}: {error.Message}", this);
            return false;
        }
    }

    private static DateTime GetLastWriteTimeUtc(string filePath)
    {
        if (string.IsNullOrEmpty(filePath))
        {
            return DateTime.MinValue;
        }

        try
        {
            return File.GetLastWriteTimeUtc(filePath);
        }
        catch
        {
            return DateTime.MinValue;
        }
    }

    private void DestroyRuntimeAssets()
    {
        if (runtimeSprite != null)
        {
            Destroy(runtimeSprite);
            runtimeSprite = null;
        }

        if (runtimeTexture != null)
        {
            Destroy(runtimeTexture);
            runtimeTexture = null;
        }
    }
}