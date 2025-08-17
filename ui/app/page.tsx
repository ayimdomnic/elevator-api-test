"use client"

import { useState, useEffect } from "react"
import { ElevatorShaft } from "@/components/elevator-shaft"
import { FloorControls } from "@/components/floor-controls"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"
import type { SystemStatus, CallElevatorRequest, CallResponse } from "@/lib/types/elevator"
import { cn } from "@/lib/utils"


const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://172.23.86.192:5000/"

export default function ElevatorManagementSystem() {
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null)
  const [activeCalls, setActiveCalls] = useState<Set<string>>(new Set())
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isConnected, setIsConnected] = useState(false)

  const totalFloors = 10



  // Fetch system status
  const fetchSystemStatus = async () => {
    try {
      setIsLoading(true)
      const response = await fetch(`${API_BASE_URL}/elevator/status`)
      const data = await response.json()
      setSystemStatus(data)
      setIsConnected(true)
      setError(null)
    } catch (err) {
      console.error("Failed to fetch system status:", err)
      setError("Failed to connect to elevator system")
      setIsConnected(false)
      toast.error("Connection lost - using demo data", {
        description: "Unable to connect to elevator system",
        action: {
          label: "Retry",
          onClick: () => fetchSystemStatus(),
        },
      })
    } finally {
      setIsLoading(false)
    }
  }

  // Call elevator
  const handleCallElevator = async (request: CallElevatorRequest) => {
    try {
      const callKey = `${request.from_floor}-${request.to_floor}`
      setActiveCalls((prev) => new Set([...prev, callKey]))

      toast.success("🚀 Elevator Called!", {
        description: `From floor ${request.from_floor} to floor ${request.to_floor}`,
        duration: 3000,
      })

      const response = await fetch(`${API_BASE_URL}/elevator/call`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
      })
      const result: CallResponse = await response.json()

      toast.success("🎯 Elevator Assigned!", {
        description: `Elevator ${result.elevator_id} is coming to floor ${request.from_floor}`,
        duration: 4000,
      })

      console.log("[v0] Elevator called:", result)

      setTimeout(() => {
        setActiveCalls((prev) => {
          const newSet = new Set(prev)
          newSet.delete(callKey)
          return newSet
        })
        toast.info("🚪 Elevator Arrived!", {
          description: `Elevator ${result.elevator_id} has arrived at floor ${request.from_floor}`,
          duration: 3000,
        })
      }, 3000)

      fetchSystemStatus()
    } catch (err) {
      console.error("Failed to call elevator:", err)
      const callKey = `${request.from_floor}-${request.to_floor}`
      setActiveCalls((prev) => {
        const newSet = new Set(prev)
        newSet.delete(callKey)
        return newSet
      })
      toast.error("❌ Call Failed", {
        description: "Unable to call elevator. Please try again.",
        action: {
          label: "Retry",
          onClick: () => handleCallElevator(request),
        },
      })
    }
  }

  // Handle floor click from shaft
  const handleFloorClick = (floor: number) => {
    handleCallElevator({ from_floor: 1, to_floor: floor })
  }

  // Auto-refresh system status
  useEffect(() => {
    fetchSystemStatus()
    const interval = setInterval(fetchSystemStatus, 5000)
    return () => clearInterval(interval)
  }, [])

  const getHealthColor = (health: string) => {
    switch (health) {
      case "healthy":
        return "bg-emerald-500 shadow-emerald-500/50"
      case "warning":
        return "bg-amber-500 shadow-amber-500/50"
      case "critical":
        return "bg-red-500 shadow-red-500/50 animate-pulse"
      default:
        return "bg-gray-500"
    }
  }

  const getHealthIcon = (health: string) => {
    switch (health) {
      case "healthy":
        return "✅"
      case "warning":
        return "⚠️"
      case "critical":
        return "🚨"
      default:
        return "❓"
    }
  }

  if (isLoading && !systemStatus) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="relative">
            <div className="animate-spin rounded-full h-16 w-16 border-4 border-primary/20 border-t-primary mx-auto"></div>
            <div className="absolute inset-0 flex items-center justify-center text-2xl">🏢</div>
          </div>
          <div className="space-y-2">
            <p className="text-lg font-semibold">Loading Elevator System...</p>
            <p className="text-muted-foreground">Connecting to building management</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <h1 className="text-4xl font-bold bg-gradient-to-r from-primary to-primary/60 bg-clip-text text-transparent">
              🏢 Elevator Management System
            </h1>
            <p className="text-muted-foreground flex items-center gap-2">
              <span className={cn("w-2 h-2 rounded-full", isConnected ? "bg-green-500 animate-pulse" : "bg-red-500")} />
              Real-time elevator monitoring and control
              {!isConnected && <span className="text-amber-500">(Demo Mode)</span>}
            </p>
          </div>

          <Card className="p-4 shadow-lg hover:shadow-xl transition-all duration-200">
            <div className="flex items-center gap-3">
              <div
                className={cn(
                  "w-4 h-4 rounded-full shadow-lg",
                  getHealthColor(systemStatus?.system_health || "healthy"),
                )}
              />
              <div>
                <div className="font-semibold flex items-center gap-1">
                  {getHealthIcon(systemStatus?.system_health || "healthy")} System Health
                </div>
                <div className="text-sm text-muted-foreground capitalize">
                  {systemStatus?.system_health || "Unknown"}
                </div>
              </div>
            </div>
          </Card>
        </div>

        {error && (
          <Card className="border-destructive shadow-lg">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 text-destructive">
                <span className="text-xl">⚠️</span>
                <span className="flex-1">{error}</span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={fetchSystemStatus}
                  className="hover:scale-105 transition-transform bg-transparent"
                >
                  🔄 Retry
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <Card className="shadow-lg hover:shadow-xl transition-shadow duration-200">
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span className="flex items-center gap-2">🏗️ Elevator Shafts</span>
                  <Badge
                    variant="secondary"
                    className={cn(
                      "transition-all duration-200",
                      (systemStatus?.active_tasks || 0) > 0 && "animate-pulse bg-blue-500 text-white",
                    )}
                  >
                    📡 {systemStatus?.active_tasks || 0} Active Tasks
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {systemStatus?.elevators ? (
                  <div className="overflow-x-auto">
                    <ElevatorShaft
                      elevators={systemStatus.elevators}
                      totalFloors={totalFloors}
                      onFloorClick={handleFloorClick}
                    />
                  </div>
                ) : (
                  <div className="text-center py-12 text-muted-foreground space-y-4">
                    <div className="text-6xl">🏢</div>
                    <div className="text-lg">No elevator data available</div>
                    <Button onClick={fetchSystemStatus} variant="outline">
                      🔄 Refresh Data
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          <div>
            <FloorControls totalFloors={totalFloors} onCallElevator={handleCallElevator} activeCalls={activeCalls} />
          </div>
        </div>
      </div>
    </div>
  )
}
