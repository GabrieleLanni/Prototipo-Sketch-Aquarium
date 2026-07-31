using System;
using System.Collections;
using System.IO;
using System.Linq;
using UnityEngine;

/// <summary>
/// Controlla periodicamente la cartella PhoneUploadServer/Uploads e mostra
/// l'ultima fotografia ricevuta in uno SpriteRenderer.
/// </summary>
public sealed class PhoneDrawingReceiver : MonoBehaviour
{
    [Header("Riferimenti")]
    [SerializeField] private SpriteRenderer targetRenderer;

    [Header("Cartella delle fotografie")]
    [Tooltip("Percorso relativo alla cartella principale del progetto Unity. Puoi anche inserire un percorso assoluto.")]
    [SerializeField] private string uploadsFolder = "PhoneUploadServer/Uploads";

    [Header("Impostazioni")]
    [Min(0.2f)]
    [SerializeField] private float checkInterval = 1f;

    [Min(0.1f)]
    [SerializeField] private float maximumWorldSize = 8f;

    [SerializeField] private bool loadLatestImageOnStart = true;

    private string resolvedUploadsFolder;
    private string lastLoadedFile;
    private Sprite runtimeSprite;
    private Texture2D runtimeTexture;
    private Coroutine monitorCoroutine;

    private static readonly string[] SupportedExtensions =
    {
        ".jpg",
        ".jpeg",
        ".png"
    };

    private void Awake()
    {
        ResolveUploadsFolder();
    }

    private void OnEnable()
    {
        monitorCoroutine = StartCoroutine(MonitorUploadsFolder());
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

    [ContextMenu("Risolvi e mostra percorso Uploads")]
    private void ResolveUploadsFolder()
    {
        if (Path.IsPathRooted(uploadsFolder))
        {
            resolvedUploadsFolder = Path.GetFullPath(uploadsFolder);
        }
        else
        {
            string projectRoot = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
            resolvedUploadsFolder = Path.GetFullPath(Path.Combine(projectRoot, uploadsFolder));
        }

        Debug.Log($"[PhoneDrawingReceiver] Cartella controllata: {resolvedUploadsFolder}", this);
    }

    private IEnumerator MonitorUploadsFolder()
    {
        if (!loadLatestImageOnStart)
        {
            lastLoadedFile = FindLatestImage();
        }

        WaitForSecondsRealtime wait = new WaitForSecondsRealtime(checkInterval);

        while (enabled)
        {
            string latestFile = FindLatestImage();

            if (!string.IsNullOrEmpty(latestFile) && latestFile != lastLoadedFile)
            {
                if (TryLoadImage(latestFile))
                {
                    lastLoadedFile = latestFile;
                }
            }

            yield return wait;
        }
    }

    private string FindLatestImage()
    {
        if (string.IsNullOrWhiteSpace(resolvedUploadsFolder))
        {
            ResolveUploadsFolder();
        }

        if (!Directory.Exists(resolvedUploadsFolder))
        {
            return null;
        }

        try
        {
            return Directory
                .EnumerateFiles(resolvedUploadsFolder)
                .Where(IsSupportedImage)
                .OrderByDescending(File.GetLastWriteTimeUtc)
                .FirstOrDefault();
        }
        catch (Exception error)
        {
            Debug.LogWarning($"[PhoneDrawingReceiver] Impossibile leggere la cartella Uploads: {error.Message}", this);
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

            Debug.Log($"[PhoneDrawingReceiver] Fotografia caricata: {Path.GetFileName(filePath)}", this);
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

    private static bool IsSupportedImage(string filePath)
    {
        string extension = Path.GetExtension(filePath);
        return SupportedExtensions.Contains(extension, StringComparer.OrdinalIgnoreCase);
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
