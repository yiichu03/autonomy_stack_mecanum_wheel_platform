#ifndef DYNAMIC_OCTOMAP_SERVER__DYNAMIC_OCTOMAP_SERVER_HPP_
#define DYNAMIC_OCTOMAP_SERVER__DYNAMIC_OCTOMAP_SERVER_HPP_

#include <cstddef>
#include <cstdint>
#include <unordered_map>
#include <vector>

#include <octomap/OcTreeKey.h>
#include <octomap_server/octomap_server.hpp>
#include <rcl_interfaces/msg/set_parameters_result.hpp>
#include <rclcpp/rclcpp.hpp>

namespace dynamic_octomap_server
{

class DynamicOctomapServer : public octomap_server::OctomapServer
{
public:
  using PCLPointCloud = octomap_server::OctomapServer::PCLPointCloud;

  explicit DynamicOctomapServer(const rclcpp::NodeOptions & node_options);

protected:
  void insertScan(
    const tf2::Vector3 & sensor_origin, const PCLPointCloud & ground,
    const PCLPointCloud & nonground) override;

private:
  struct VoxelEvidence
  {
    int hit_count = 0;
    int free_observation_count = 0;
    double last_hit_time = 0.0;
    bool stable = false;
  };

  struct OcTreeKeyHash
  {
    std::size_t operator()(const octomap::OcTreeKey & key) const;
  };

  struct OcTreeKeyEqual
  {
    bool operator()(const octomap::OcTreeKey & lhs, const octomap::OcTreeKey & rhs) const;
  };

  using EvidenceMap =
    std::unordered_map<octomap::OcTreeKey, VoxelEvidence, OcTreeKeyHash, OcTreeKeyEqual>;

  void computeScanEvidence(
    const tf2::Vector3 & sensor_origin, const PCLPointCloud & ground,
    const PCLPointCloud & nonground, octomap::KeySet & free_cells,
    octomap::KeySet & occupied_cells);

  void updateDynamicEvidence(
    const octomap::KeySet & free_cells, const octomap::KeySet & occupied_cells);

  bool clearKey(const octomap::OcTreeKey & key);

  rcl_interfaces::msg::SetParametersResult onDynamicParameters(
    const std::vector<rclcpp::Parameter> & parameters);

  bool dynamic_enabled_ = true;
  int free_observation_threshold_ = 2;
  double stale_time_ = 3.0;
  int stable_hit_threshold_ = 4;
  int stable_free_observation_threshold_ = 6;
  int force_free_updates_ = 4;

  EvidenceMap evidence_;
  rclcpp::node_interfaces::OnSetParametersCallbackHandle::SharedPtr dynamic_param_callback_;
};

}  // namespace dynamic_octomap_server

#endif  // DYNAMIC_OCTOMAP_SERVER__DYNAMIC_OCTOMAP_SERVER_HPP_
