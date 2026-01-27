<script>
  let file = null;
  let loading = false;
  let error = "";
  let data = null;

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
    try {
      history.back();
    } catch {
      window.location.href = "/";
    }
  }

  const CAL_FORMULA = "kcal = (kcal/100g) × (gramas_estimadas/100)";
  const WASTE_FORMULA = "W = FoodArea / (PlateArea − GarbageArea) × 100";
</script>

<main class="w-screen min-h-screen bg-zinc-900 text-zinc-200 px-6 py-10">
  <div class="w-full max-w-[1950px] mx-auto space-y-6">

    <div class="flex items-start justify-between gap-4">
      <button
        class="px-4 py-2 rounded-xl font-semibold border border-zinc-700 hover:border-zinc-500 hover:opacity-90"
        on:click={goBack}
      >
        ← Voltar
      </button>

      <div class="text-right">
        <h1 class="text-2xl sm:text-3xl font-bold">Contador de Calorias</h1>
        <p class="text-sm text-zinc-400">
          Upload → deteção → estimativa por porção (área relativa no prato)
        </p>
      </div>
    </div>

    <!-- BODY GRID -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">

      <!-- LEFT CARD: fórmulas + explicação -->
      <aside class="lg:col-span-4 rounded-2xl border border-zinc-800 bg-zinc-950/30 p-5 space-y-4">
        <div>
          <h2 class="font-semibold text-lg">
            <span class="text-red-700">Como</span> calculamos
          </h2>
          <p class="text-sm text-zinc-400 mt-1">
            Resumo simples das regras usadas para estimar calorias e desperdício.
          </p>
        </div>

        <div class="space-y-2">
          <p class="text-sm">
            <span class="text-red-700 font-semibold">Calorias</span>
          </p>
          <div class="font-mono text-sm rounded-xl border border-zinc-800 bg-zinc-900/40 p-3">
            {CAL_FORMULA}
          </div>
          <ul class="text-sm text-zinc-400 list-disc pl-5 space-y-1">
            <li><b>kcal/100g</b> vem do mapa de alimentos.</li>
            <li><b>gramas_estimadas</b> é a porção estimada pela área relativa no prato.</li>
            <li>Usamos limites de sanidade para evitar valores absurdos.</li>
          </ul>
        </div>

        <div class="space-y-2 pt-2 border-t border-zinc-800">
          <p class="text-sm">
            <span class="text-red-700 font-semibold">Desperdício</span>
          </p>
          <div class="font-mono text-sm rounded-xl border border-zinc-800 bg-zinc-900/40 p-3">
            {WASTE_FORMULA}
          </div>
          <ul class="text-sm text-zinc-400 list-disc pl-5 space-y-1">
            <li>Calculado em <b>pixéis</b> a partir das deteções.</li>
            <li>Utensílios e “garbage” são ignorados.</li>
            <li>O prato é a referência para normalizar a área.</li>
          </ul>
        </div>

        <!-- opcional: mostrar fórmula “com números” quando houver data -->
        {#if data}
          <div class="pt-2 border-t border-zinc-800 space-y-2">
            <p class="text-sm">
              <span class="text-red-700 font-semibold">Valores atuais</span>
            </p>
            <div class="text-sm text-zinc-400 space-y-1">
              <div>FoodArea: <b class="text-zinc-200">{(data.food_area ?? 0).toFixed(2)}</b></div>
              <div>PlateArea: <b class="text-zinc-200">{(data.plate_area ?? 0).toFixed(2)}</b></div>
              <div>GarbageArea: <b class="text-zinc-200">{(data.garbage_area ?? 0).toFixed(2)}</b></div>
            </div>
          </div>
        {/if}
      </aside>

      <!-- CENTER: upload + resultados -->
      <section class="lg:col-span-8 rounded-2xl border border-zinc-800 bg-zinc-950/30 p-6 space-y-4">

        <!-- Upload + botão -->
        <div class="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div class="w-full">
            <label class="block text-sm font-semibold mb-1">
              <span class="text-red-700">Imagem</span> (.jpg, .jpeg, .png, .avif)
            </label>
            <input
              class="block w-full text-sm text-zinc-200 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0
                     file:bg-zinc-200 file:text-zinc-900 hover:file:opacity-90"
              type="file"
              accept="image/*"
              on:change={onFileChange}
            />
          </div>

          <button
            class="px-6 py-3 rounded-xl font-semibold border border-zinc-700 hover:border-zinc-500 hover:opacity-90 disabled:opacity-50"
            on:click={calculate}
            disabled={loading || !file}
          >
            {loading ? "A calcular..." : "Calcular"}
          </button>
        </div>

        {#if error}
          <p class="text-red-500">{error}</p>
        {/if}

        {#if data}
          <!-- Cards -->
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div class="rounded-xl border border-zinc-800 p-4 bg-zinc-900/20">
              <div class="text-sm text-zinc-400">Desperdício</div>
              <div class="text-3xl font-bold">
                {(data.waste_percentage ?? 0).toFixed(1)}%
              </div>
              <div class="text-xs text-zinc-400 mt-1">
                Estimado pela área dos alimentos no prato (pixéis).
              </div>
            </div>

            <div class="rounded-xl border border-zinc-800 p-4 bg-zinc-900/20">
              <div class="text-sm text-zinc-400">Calorias totais</div>
              <div class="text-3xl font-bold">
                {(data.calories?.total ?? 0).toFixed(2)} kcal
              </div>
              <div class="text-xs text-zinc-400 mt-1">
                Baseado em kcal/100g e porção estimada.
              </div>
            </div>
          </div>

          <!-- Botão imagens -->
          <div class="flex flex-wrap gap-2">
            <button
              class="px-4 py-2 rounded-xl font-semibold border border-zinc-700 hover:border-zinc-500 hover:opacity-90"
              on:click={() => (showImages = !showImages)}
            >
              {showImages ? "Ocultar imagens" : "Ver imagens de deteção"}
            </button>
          </div>

          <!-- Detalhe por alimento -->
          <div class="rounded-xl border border-zinc-800 p-4 bg-zinc-900/20">
            <h2 class="font-semibold mb-2">
              <span class="text-red-700">Detalhe</span> por alimento
            </h2>

            {#if (data.calories?.items?.length ?? 0) === 0}
              <p class="text-sm text-zinc-400">
                Nenhum alimento estimado (confere se foi detetado e se existe no calorie_map.json).
              </p>
            {:else}
              <ul class="space-y-2">
                {#each data.calories.items as it}
                  <li class="flex flex-col sm:flex-row sm:justify-between gap-1 border border-zinc-800 rounded-xl p-3 bg-zinc-950/20">
                    <span class="font-semibold">{it.label_name}</span>

                    <span class="text-sm text-zinc-400">
                      conf: {(it.confidence * 100).toFixed(1)}%
                      · porção: {(it.portion_ratio * 100).toFixed(1)}%
                      · g: {it.grams_est}
                      · kcal/100g: {it.kcal_per_100g}
                      · kcal: <b class="text-zinc-200">{it.kcal_estimated}</b>
                    </span>
                  </li>
                {/each}
              </ul>
            {/if}
          </div>

          <!-- Imagens -->
          {#if showImages}
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
              {#if data.image_base64}
                <div class="rounded-xl border border-zinc-800 p-4 bg-zinc-900/20 space-y-2">
                  <h2 class="font-semibold">
                    <span class="text-red-700">Imagem</span> com deteções
                  </h2>
                  <img class="rounded-xl w-full" src={`data:image/jpeg;base64,${data.image_base64}`} alt="detections" />
                </div>
              {/if}

              {#if data.clustering_image_base64}
                <div class="rounded-xl border border-zinc-800 p-4 bg-zinc-900/20 space-y-2">
                  <h2 class="font-semibold">
                    <span class="text-red-700">Clustering</span>
                  </h2>
                  <img class="rounded-xl w-full" src={`data:image/jpeg;base64,${data.clustering_image_base64}`} alt="clustering" />
                </div>
              {/if}
            </div>
          {/if}
        {/if}
      </section>
    </div>
  </div>
</main>
