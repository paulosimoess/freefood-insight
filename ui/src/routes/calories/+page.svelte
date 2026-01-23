<script>
  let file = null;
  let loading = false;
  let error = "";
  let data = null;

  const API_BASE = import.meta.env.VITE_API_BASE ?? "";

  function onFileChange(e) {
    error = "";
    data = null;
    file = e.target.files?.[0] ?? null;
  }

  async function calculate() {
    if (!file) {
      error = "Seleciona uma imagem primeiro.";
      return;
    }

    loading = true;
    error = "";
    data = null;

    try {
      const fd = new FormData();
      fd.append("file", file);

      const res = await fetch(`${API_BASE}/api/calories`, {
        method: "POST",
        body: fd
      });

      if (!res.ok) {
        const txt = await res.text();
        throw new Error(txt || `Erro HTTP ${res.status}`);
      }

      data = await res.json();
    } catch (e) {
      error = e?.message ?? "Erro ao calcular calorias";
    } finally {
      loading = false;
    }
  }

  const DEFAULT_FORMULA =
    "(kcal_100g/100) × grams_est × confidence, onde grams_est = portion_ratio × grams_per_plate";
</script>

<main class="min-h-screen flex items-center justify-center px-6 py-10">
  <div class="w-full max-w-3xl space-y-6">
    <div class="text-center space-y-2">
      <h1 class="text-3xl font-bold">Contador de Calorias</h1>
      <p class="text-muted-foreground">
        Upload de imagem → deteção → estimativa por porção (área no prato).
      </p>
    </div>

    <div class="rounded-2xl border p-6 space-y-4">
      <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <input class="block w-full text-sm" type="file" accept="image/*" on:change={onFileChange} />

        <button
          class="inline-block px-6 py-3 rounded-xl font-semibold border hover:opacity-90 disabled:opacity-50"
          on:click={calculate}
          disabled={loading || !file}
        >
          {loading ? "A calcular..." : "Calcular calorias"}
        </button>
      </div>

      {#if error}
        <p class="text-red-600">{error}</p>
      {/if}

      {#if data}
        <div class="space-y-4">
          <div class="rounded-xl border p-4">
            <div class="text-lg font-semibold">
              Total: <span class="font-bold">{data.calories?.total ?? 0}</span> kcal
            </div>
            <div class="text-sm text-muted-foreground">
              {data.calories?.formula ?? DEFAULT_FORMULA}
            </div>
          </div>

          <div class="rounded-xl border p-4">
            <h2 class="font-semibold mb-2">Detalhe por alimento</h2>

            {#if (data.calories?.items?.length ?? 0) === 0}
              <p class="text-sm text-muted-foreground">
                Nenhum alimento estimado (confere se o alimento tem kcal no calorie_map.json e se foi detetado).
              </p>
            {:else}
              <ul class="space-y-2">
                {#each data.calories.items as it}
                  <li class="flex flex-col sm:flex-row sm:justify-between gap-1">
                    <span class="font-medium">{it.label_name}</span>

                    <span class="text-sm text-muted-foreground">
                      conf: {(it.confidence * 100).toFixed(1)}%
                      · porção: {(it.portion_ratio * 100).toFixed(1)}%
                      · g: {it.grams_est}
                      · kcal/100g: {it.kcal_per_100g}
                      · kcal: <b>{it.kcal_estimated}</b>
                    </span>
                  </li>
                {/each}
              </ul>
            {/if}
          </div>

          {#if data.image_base64}
            <div class="rounded-xl border p-4 space-y-2">
              <h2 class="font-semibold">Imagem com deteções</h2>
              <img class="rounded-xl max-w-full" src={`data:image/jpeg;base64,${data.image_base64}`} alt="detections" />
            </div>
          {/if}

          {#if data.clustering_image_base64}
            <div class="rounded-xl border p-4 space-y-2">
              <h2 class="font-semibold">Clustering</h2>
              <img class="rounded-xl max-w-full" src={`data:image/jpeg;base64,${data.clustering_image_base64}`} alt="clustering" />
            </div>
          {/if}
        </div>
      {/if}
    </div>

    <div class="text-center">
      <a href="/" class="inline-block px-6 py-3 rounded-xl font-semibold border hover:opacity-90">
        Voltar ao menu
      </a>
    </div>
  </div>
</main>
