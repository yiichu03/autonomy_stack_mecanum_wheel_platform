#include "dynamic_octomap_server/dynamic_octomap_server.hpp"

#include <octomap_ros/conversions.hpp>

#include <algorithm>
#include <functional>
#include <memory>
#include <string>

namespace dynamic_octomap_server
{

namespace
{

int atLeastOne(int64_t value)
{
  return static_cast<int>(std::max<int64_t>(1, value));
}

int nonNegativeInt(int64_t value)
{
  return static_cast<int>(std::max<int64_t>(0, value));
}

double nonNegativeDouble(double value)
{
  return std::max(0.0, value);
}

bool getDoubleParameter(const rclcpp::Parameter & parameter, double & value)
{
  if (parameter.get_type() == rclcpp::ParameterType::PARAMETER_DOUBLE) {
    value = parameter.as_double();
    return true;
  }
  if (parameter.get_type() == rclcpp::ParameterType::PARAMETER_INTEGER) {
    value = static_cast<double>(parameter.as_int());
    return true;
  }
  return false;
}

}  // namespace

std::size_t DynamicOctomapServer::OcTreeKeyHash::operator()(const octomap::OcTreeKey & key) const
{
  std::size_t seed = 0;
  for (unsigned int i = 0; i < 3; ++i) {
    seed ^= std::hash<octomap::key_type>{}(key[i]) + 0x9e3779b9 + (seed << 6) + (seed >> 2);
  }
  return seed;
}

bool DynamicOctomapServer::OcTreeKeyEqual::operator()(
  const octomap::OcTreeKey & lhs, const octomap::OcTreeKey & rhs) const
{
  return lhs[0] == rhs[0] && lhs[1] == rhs[1] && lhs[2] == rhs[2];
}

DynamicOctomapServer::DynamicOctomapServer(const rclcpp::NodeOptions & node_options)
: OctomapServer(node_options)
{
  dynamic_enabled_ = declare_parameter("dynamic_clearing.enabled", dynamic_enabled_);
  free_observation_threshold_ = atLeastOne(
    declare_parameter("dynamic_clearing.free_observation_threshold", free_observation_threshold_));
  stale_time_ = nonNegativeDouble(declare_parameter("dynamic_clearing.stale_time", stale_time_));
  stable_hit_threshold_ =
    atLeastOne(declare_parameter("dynamic_clearing.stable_hit_threshold", stable_hit_threshold_));
  stable_free_observation_threshold_ = atLeastOne(
    declare_parameter(
      "dynamic_clearing.stable_free_observation_threshold",
      stable_free_observation_threshold_));
  force_free_updates_ =
    nonNegativeInt(declare_parameter("dynamic_clearing.force_free_updates", force_free_updates_));

  dynamic_param_callback_ = add_on_set_parameters_callback(
    std::bind(&DynamicOctomapServer::onDynamicParameters, this, std::placeholders::_1));

  RCLCPP_INFO(
    get_logger(),
    "Dynamic clearing: enabled=%s free_threshold=%d stale_time=%.2f stable_hits=%d "
    "stable_free_threshold=%d force_free_updates=%d",
    dynamic_enabled_ ? "true" : "false", free_observation_threshold_, stale_time_,
    stable_hit_threshold_, stable_free_observation_threshold_, force_free_updates_);
}

void DynamicOctomapServer::insertScan(
  const tf2::Vector3 & sensor_origin, const PCLPointCloud & ground,
  const PCLPointCloud & nonground)
{
  octomap::KeySet free_cells;
  octomap::KeySet occupied_cells;

  if (dynamic_enabled_) {
    computeScanEvidence(sensor_origin, ground, nonground, free_cells, occupied_cells);
  }

  OctomapServer::insertScan(sensor_origin, ground, nonground);

  if (dynamic_enabled_) {
    updateDynamicEvidence(free_cells, occupied_cells);
  }
}

void DynamicOctomapServer::computeScanEvidence(
  const tf2::Vector3 & sensor_origin_tf, const PCLPointCloud & ground,
  const PCLPointCloud & nonground, octomap::KeySet & free_cells,
  octomap::KeySet & occupied_cells)
{
  const auto sensor_origin = octomap::pointTfToOctomap(sensor_origin_tf);
  octomap::KeyRay key_ray;

  for (const auto & pcl_point : ground) {
    octomap::point3d point(pcl_point.x, pcl_point.y, pcl_point.z);
    if ((max_range_ > 0.0) && ((point - sensor_origin).norm() > max_range_)) {
      point = sensor_origin + (point - sensor_origin).normalized() * max_range_;
    }

    if (octree_->computeRayKeys(sensor_origin, point, key_ray)) {
      free_cells.insert(key_ray.begin(), key_ray.end());
    }
  }

  for (const auto & pcl_point : nonground) {
    octomap::point3d point(pcl_point.x, pcl_point.y, pcl_point.z);
    const double point_range = (point - sensor_origin).norm();

    if ((max_range_ < 0.0) || (point_range <= max_range_)) {
      if (octree_->computeRayKeys(sensor_origin, point, key_ray)) {
        free_cells.insert(key_ray.begin(), key_ray.end());
      }

      octomap::OcTreeKey key;
      if (octree_->coordToKeyChecked(point, key)) {
        occupied_cells.insert(key);
      }
    } else if (max_range_ > 0.0) {
      octomap::point3d clipped_point =
        sensor_origin + (point - sensor_origin).normalized() * max_range_;
      if (octree_->computeRayKeys(sensor_origin, clipped_point, key_ray)) {
        free_cells.insert(key_ray.begin(), key_ray.end());

        octomap::OcTreeKey end_key;
        if (octree_->coordToKeyChecked(clipped_point, end_key)) {
          free_cells.insert(end_key);
        }
      }
    }
  }
}

void DynamicOctomapServer::updateDynamicEvidence(
  const octomap::KeySet & free_cells, const octomap::KeySet & occupied_cells)
{
  const double stamp = now().seconds();
  octomap::KeySet keys_to_clear;

  for (const auto & key : occupied_cells) {
    auto & evidence = evidence_[key];
    evidence.hit_count = std::min(evidence.hit_count + 1, stable_hit_threshold_);
    evidence.free_observation_count = 0;
    evidence.last_hit_time = stamp;
    if (evidence.hit_count >= stable_hit_threshold_) {
      evidence.stable = true;
    }
  }

  for (const auto & key : free_cells) {
    if (occupied_cells.find(key) != occupied_cells.end()) {
      continue;
    }

    auto evidence_it = evidence_.find(key);
    if (evidence_it == evidence_.end()) {
      continue;
    }

    VoxelEvidence & evidence = evidence_it->second;
    evidence.free_observation_count += 1;

    const int threshold = evidence.stable ?
      stable_free_observation_threshold_ : free_observation_threshold_;
    if (evidence.free_observation_count >= threshold) {
      keys_to_clear.insert(key);
    }
  }

  if (stale_time_ > 0.0) {
    for (const auto & evidence_entry : evidence_) {
      const VoxelEvidence & evidence = evidence_entry.second;
      if (evidence.stable || evidence.free_observation_count == 0) {
        continue;
      }
      if ((stamp - evidence.last_hit_time) >= stale_time_) {
        keys_to_clear.insert(evidence_entry.first);
      }
    }
  }

  for (const auto & key : keys_to_clear) {
    if (clearKey(key)) {
      evidence_.erase(key);
    }
  }

  if (!keys_to_clear.empty() && compress_map_) {
    octree_->prune();
  }
}

bool DynamicOctomapServer::clearKey(const octomap::OcTreeKey & key)
{
  auto * node = octree_->search(key);
  if (node == nullptr) {
    return true;
  }

  if (!octree_->isNodeOccupied(node)) {
    return true;
  }

  for (int i = 0; i < force_free_updates_; ++i) {
    octree_->updateNode(key, false);
  }

  node = octree_->search(key);
  if (node != nullptr && octree_->isNodeOccupied(node)) {
    octree_->setNodeValue(key, octree_->getClampingThresMinLog());
  }

  updateMinKey(key, update_bbox_min_);
  updateMaxKey(key, update_bbox_max_);
  return true;
}

rcl_interfaces::msg::SetParametersResult DynamicOctomapServer::onDynamicParameters(
  const std::vector<rclcpp::Parameter> & parameters)
{
  auto enabled = dynamic_enabled_;
  auto free_observation_threshold = free_observation_threshold_;
  auto stale_time = stale_time_;
  auto stable_hit_threshold = stable_hit_threshold_;
  auto stable_free_observation_threshold = stable_free_observation_threshold_;
  auto force_free_updates = force_free_updates_;

  rcl_interfaces::msg::SetParametersResult result;
  result.successful = true;

  for (const auto & parameter : parameters) {
    const std::string & name = parameter.get_name();

    if (name == "dynamic_clearing.enabled") {
      if (parameter.get_type() != rclcpp::ParameterType::PARAMETER_BOOL) {
        result.successful = false;
        result.reason = "dynamic_clearing.enabled must be a bool";
        return result;
      }
      enabled = parameter.as_bool();
    } else if (name == "dynamic_clearing.free_observation_threshold") {
      if (parameter.get_type() != rclcpp::ParameterType::PARAMETER_INTEGER) {
        result.successful = false;
        result.reason = "dynamic_clearing.free_observation_threshold must be an integer";
        return result;
      }
      free_observation_threshold = atLeastOne(parameter.as_int());
    } else if (name == "dynamic_clearing.stale_time") {
      double value = stale_time;
      if (!getDoubleParameter(parameter, value)) {
        result.successful = false;
        result.reason = "dynamic_clearing.stale_time must be numeric";
        return result;
      }
      stale_time = nonNegativeDouble(value);
    } else if (name == "dynamic_clearing.stable_hit_threshold") {
      if (parameter.get_type() != rclcpp::ParameterType::PARAMETER_INTEGER) {
        result.successful = false;
        result.reason = "dynamic_clearing.stable_hit_threshold must be an integer";
        return result;
      }
      stable_hit_threshold = atLeastOne(parameter.as_int());
    } else if (name == "dynamic_clearing.stable_free_observation_threshold") {
      if (parameter.get_type() != rclcpp::ParameterType::PARAMETER_INTEGER) {
        result.successful = false;
        result.reason =
          "dynamic_clearing.stable_free_observation_threshold must be an integer";
        return result;
      }
      stable_free_observation_threshold = atLeastOne(parameter.as_int());
    } else if (name == "dynamic_clearing.force_free_updates") {
      if (parameter.get_type() != rclcpp::ParameterType::PARAMETER_INTEGER) {
        result.successful = false;
        result.reason = "dynamic_clearing.force_free_updates must be an integer";
        return result;
      }
      force_free_updates = nonNegativeInt(parameter.as_int());
    }
  }

  dynamic_enabled_ = enabled;
  free_observation_threshold_ = free_observation_threshold;
  stale_time_ = stale_time;
  stable_hit_threshold_ = stable_hit_threshold;
  stable_free_observation_threshold_ = stable_free_observation_threshold;
  force_free_updates_ = force_free_updates;

  return result;
}

}  // namespace dynamic_octomap_server

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<dynamic_octomap_server::DynamicOctomapServer>(
    rclcpp::NodeOptions{});
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
