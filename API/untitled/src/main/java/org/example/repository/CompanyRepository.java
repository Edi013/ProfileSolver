package org.example.repository;

import org.example.model.Company;
import org.springframework.data.elasticsearch.repository.ElasticsearchRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface CompanyRepository extends ElasticsearchRepository<Company, String> {

    List<Company> findByNamesContainingIgnoreCaseOrEmailContainingIgnoreCaseOrPhoneContainingIgnoreCase(String names, String email, String phone);
}
