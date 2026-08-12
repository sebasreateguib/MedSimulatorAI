"use client";

import { BarChart3, ClipboardCheck, History, Home, LogOut, Stethoscope } from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { NavMain, type NavItem } from "@/components/shadcn-space/blocks/sidebar-01/nav-main";
import { cn } from "@/lib/utils";
import type { UsuarioPublico } from "@/types";

/**
 * En modo icono la barra mide 3rem (48px): un px-4 a cada lado dejaría 16px
 * para botones de 32px. El padding tiene que encogerse junto con la barra.
 */
const PADDING_LATERAL = "px-4 group-data-[collapsible=icon]:px-2";

interface AppSidebarProps {
  onIrInicio: () => void;
  onNuevoCaso: () => void;
  onVerEvaluacion: () => void;
  onVerHistorial: () => void;
  onVerMetricas: () => void;
  tieneEvaluacion: boolean;
  usuario: UsuarioPublico | null;
  onSalir: () => void;
}

export function AppSidebar({
  onIrInicio,
  onNuevoCaso,
  onVerEvaluacion,
  onVerHistorial,
  onVerMetricas,
  tieneEvaluacion,
  usuario,
  onSalir,
}: AppSidebarProps) {
  const navData: NavItem[] = [
    { label: "Simulador", isSection: true },
    { title: "Inicio", icon: Home, href: "#", onClick: onIrInicio },
    { title: "Nuevo caso", icon: Stethoscope, href: "#", onClick: onNuevoCaso },
    ...(tieneEvaluacion
      ? [{ title: "Evaluación", icon: ClipboardCheck, href: "#", onClick: onVerEvaluacion }]
      : []),

    { label: "Analítica", isSection: true },
    { title: "Historial", icon: History, href: "#", onClick: onVerHistorial },
    { title: "Métricas de uso", icon: BarChart3, href: "#", onClick: onVerMetricas },
  ];

  return (
    <Sidebar collapsible="icon" className="px-0 h-full [&_[data-slot=sidebar-inner]]:h-full">
      <SidebarHeader className={cn("pt-3 pb-1", PADDING_LATERAL)}>
        <SidebarMenu>
          <SidebarMenuItem className="flex items-center justify-between gap-2 group-data-[collapsible=icon]:justify-center">
            <MarcaSidebar className="group-data-[collapsible=icon]:hidden" />
            <SidebarTrigger className="shrink-0 text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-foreground" />
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      {/* SidebarContent ya es flex-1 con overflow propio: no necesita una
          altura fija, que además empujaría el pie fuera de la pantalla. */}
      <SidebarContent className={cn("mt-2", PADDING_LATERAL)}>
        <NavMain items={navData} />
      </SidebarContent>

      <SidebarFooter className={cn("border-t border-sidebar-border py-3", PADDING_LATERAL)}>
        {usuario && (
          <div className="min-w-0 px-1 group-data-[collapsible=icon]:hidden">
            <p className="truncate text-[13px] text-sidebar-foreground">{usuario.username}</p>
            <p className="truncate font-mono text-[10px] text-sidebar-foreground/55">
              {usuario.email}
            </p>
          </div>
        )}
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              tooltip="Cerrar sesión"
              onClick={onSalir}
              className="h-9 cursor-pointer rounded-md px-3 py-2 text-sm font-medium group-data-[collapsible=icon]:size-8! group-data-[collapsible=icon]:p-2!"
            >
              <LogOut size={16} />
              <span>Cerrar sesión</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}

function MarcaSidebar({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-2.5 px-1 py-1", className)}>
      {/* Cruz clínica invertida: sobre la placa oscura el cuadrado va claro. */}
      <span className="relative block h-7 w-7 shrink-0 bg-sidebar-foreground">
        <span className="absolute inset-y-[3px] inset-x-[9px] bg-sidebar" />
        <span className="absolute inset-x-[3px] inset-y-[9px] bg-sidebar" />
      </span>
      <div className="leading-none">
        <p
          className="text-[15px] tracking-tight text-sidebar-foreground"
          style={{ fontFamily: "var(--serif-display)" }}
        >
          MedSimulator AI
        </p>
        <p className="mt-1 font-mono text-[9px] uppercase tracking-[0.14em] text-sidebar-foreground/55">
          Simulación clínica
        </p>
      </div>
    </div>
  );
}
