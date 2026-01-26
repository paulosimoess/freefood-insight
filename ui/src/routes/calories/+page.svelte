<script>
  let file = null;
  let loading = false;
  let error = "";
  let data = null;

  let showInfo = false;
  let showImages = false;

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
      error = e?.message ?? "Erro ao calcular";
    } finally {
      loading = false;
    }
  }

  function goBack() {
    // volta na navegação, se falhar vai ao menu
    try {
      history.back();
    } catch {
      window.location.href = "/";
    }
  }

  const WASTE_FORMULA = "W = FoodArea / (PlateArea − GarbageArea) × 100";
  const CAL_FORMULA = "kcal = (kcal/100g) × (gramas_estimadas / 100)";
</script>

<main class="min-h-screen flex items-center justify-center px-6 py-10">
  <div class="w-full max-w-4xl space-y-6">
    <!-- Top bar -->
    <div class="flex items-center justify-between">
      <button
        class="px-4 py-2 rounded-xl font-semibold border hover:opacity-90"
        on:click={goBack}
      >
        ← Voltar
      </button>

      <div class="text-right">
        <h1 class="text-2xl sm:text-3xl font-bold">Contador de Calorias</h1>
        <p class="text-sm text-muted-foreground">
          Upload → deteção → estimativa por porção (área relativa no prato)
        </p>
      </div>
    </div>

    <!-- Upload + action -->
    <div class="rounded-2xl border p-6 space-y-4 bg-white/50">
      <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <input class="block w-full text-sm" type="file" accept="image/*" on:change={onFileChange} />

        <button
          class="inline-block px-6 py-3 rounded-xl font-semibold border hover:opacity-90 disabled:opacity-50"
          on:click={calculate}
          disabled={loading || !file}
        >
          {loading ? "A calcular..." : "Calcular"}
        </button>
      </div>

      {#if error}
        <p class="text-red-600">{error}</p>
      {/if}

      {#if data}
        <!-- Summary cards -->
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div class="rounded-xl border p-4 bg-white">
            <div class="text-sm text-muted-foreground">Desperdício</div>
            <div class="text-3xl font-bold">
              {(data.waste_percentage ?? 0).toFixed(1)}%
            </div>
            <div class="text-xs text-muted-foreground mt-1">
              Estimado pela área dos alimentos no prato (em pixéis).
            </div>
          </div>

          <div class="rounded-xl border p-4 bg-white">
            <div class="text-sm text-muted-foreground">Calorias totais</div>
            <div class="text-3xl font-bold">
              {(data.calories?.total ?? 0).toFixed(2)} kcal
            </div>
            <div class="text-xs text-muted-foreground mt-1">
              Baseado em kcal/100g e gramas estimadas pela porção.
            </div>
          </div>
        </div>

        <!-- Actions -->
        <div class="flex flex-wrap gap-2">
          <button
            class="px-4 py-2 rounded-xl font-semibold border hover:opacity-90"
            on:click={() => (showInfo = !showInfo)}
          >
            {showInfo ? "Ocultar explicação" : "Ver explicação e fórmulas"}
          </button>

          <button
            class="px-4 py-2 rounded-xl font-semibold border hover:opacity-90"
            on:click={() => (showImages = !showImages)}
          >
            {showImages ? "Ocultar imagens" : "Ver imagens de deteção"}
          </button>
        </div>

        <!-- Info (texto estilo slide, simplificado) -->
        {#if showInfo}
          <div class="rounded-xl border p-4 bg-white space-y-3">
            <h2 class="font-semibold text-lg">Como é calculado</h2>

            <ul class="list-disc pl-5 text-sm text-muted-foreground space-y-1">
              <li>
                O desperdício (%) usa a <b>área dos alimentos</b> detetados no prato,
                excluindo utensílios (garfo, faca, colher, copo...) e <b>garbage</b>.
              </li>
              <li>
                As áreas são medidas em <b>pixéis</b> a partir das deteções do modelo.
              </li>
              <li>
                As calorias são uma <b>estimativa</b> baseada em kcal/100g e na porção (área relativa).
              </li>
            </ul>

            <div class="space-y-2">
              <div class="text-sm font-semibold">Fórmula do desperdício</div>
              <div class="font-mono text-sm rounded-xl border bg-gray-50 p-3">
                {WASTE_FORMULA}
              </div>
            </div>

            <div class="space-y-2">
              <div class="text-sm font-semibold">Fórmula das calorias</div>
              <div class="font-mono text-sm rounded-xl border bg-gray-50 p-3">
                {CAL_FORMULA}
              </div>
              <div class="text-xs text-muted-foreground">
                Nota: as gramas são aproximadas e dependem da porção estimada.
              </div>
            </div>
          </div>
        {/if}

        <!-- Detail per food -->
        <div class="rounded-xl border p-4 bg-white">
          <h2 class="font-semibold mb-2">Detalhe por alimento</h2>

          {#if (data.calories?.items?.length ?? 0) === 0}
            <p class="text-sm text-muted-foreground">
              Nenhum alimento estimado (confere se foi detetado e se existe no calorie_map.json).
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

        <!-- Images hidden by default -->
        {#if showImages}
          {#if data.image_base64}
            <div class="rounded-xl border p-4 space-y-2 bg-white">
              <h2 class="font-semibold">Imagem com deteções</h2>
              <img class="rounded-xl max-w-full" src={`data:image/jpeg;base64,${data.image_base64}`} alt="detections" />
            </div>
          {/if}

          {#if data.clustering_image_base64}
            <div class="rounded-xl border p-4 space-y-2 bg-white">
              <h2 class="font-semibold">Clustering</h2>
              <img class="rounded-xl max-w-full" src={`data:image/jpeg;base64,${data.clustering_image_base64}`} alt="clustering" />
            </div>
          {/if}
        {/if}
      {/if}
    </div>

    <!-- Bottom link (opcional, podes remover se quiseres) -->
    <div class="text-center">
      <a href="/" class="inline-block px-6 py-3 rounded-xl font-semibold border hover:opacity-90">
        Voltar ao menu
      </a>
    </div>
  </div>
</main>
