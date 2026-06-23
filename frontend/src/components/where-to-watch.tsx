"use client";

import { useQuery } from "@tanstack/react-query";
import Image from "next/image";

import { api } from "@/lib/api";

interface Provider {
  provider_id: number;
  provider_name: string;
  logo_path: string | null;
}

interface ProvidersResponse {
  country: string;
  link: string | null;
  flatrate: Provider[];
  rent: Provider[];
  buy: Provider[];
}

const TMDB_LOGO = "https://image.tmdb.org/t/p/original";

function ProviderRow({ label, providers }: { label: string; providers: Provider[] }) {
  if (providers.length === 0) return null;
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <span className="text-xs text-muted-foreground w-12 shrink-0">{label}</span>
      <div className="flex gap-2 flex-wrap">
        {providers.map((p) => (
          <div
            key={p.provider_id}
            className="h-9 w-9 rounded-md overflow-hidden bg-muted relative shrink-0"
            title={p.provider_name}
          >
            {p.logo_path ? (
              <Image
                src={`${TMDB_LOGO}${p.logo_path}`}
                alt={p.provider_name}
                fill
                sizes="36px"
                className="object-cover"
              />
            ) : (
              <span className="text-[10px] flex h-full items-center justify-center">
                {p.provider_name.slice(0, 3)}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export function WhereToWatch({ tmdbId }: { tmdbId: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ["providers", tmdbId],
    queryFn: async () => {
      const resp = await api.get<ProvidersResponse>(`/api/v1/movies/${tmdbId}/providers`);
      return resp.data;
    },
  });

  if (isLoading) {
    return <div className="h-9 w-32 bg-muted rounded animate-pulse" />;
  }
  if (!data) return null;

  const hasAny = data.flatrate.length + data.rent.length + data.buy.length > 0;
  if (!hasAny) {
    return (
      <p className="text-xs text-muted-foreground">
        No streaming info available for {data.country}.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-baseline gap-2">
        <h3 className="text-sm font-medium">Where to watch</h3>
        {data.link && (
          <a
            href={data.link}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-muted-foreground hover:text-primary"
          >
            (full list →)
          </a>
        )}
      </div>
      <ProviderRow label="Stream" providers={data.flatrate} />
      <ProviderRow label="Rent" providers={data.rent} />
      <ProviderRow label="Buy" providers={data.buy} />
      <p className="text-[10px] text-muted-foreground">
        Source: JustWatch via TMDB · {data.country}
      </p>
    </div>
  );
}
